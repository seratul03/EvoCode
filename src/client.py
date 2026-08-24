import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
import openai
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from evoflow.rate_limiter import TokenBucketRateLimiter
from evoflow.budget_tracker import CallBudgetTracker, BudgetExceededError

# Setup logging
logger = logging.getLogger(__name__)

# Resolve the project root relative to this file to load the .env file
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path, override=True)

class EvoClient:
    """
    EvoClient handles calling LLM APIs (Groq and OpenRouter) asynchronously
    with built-in rate-limiting, tenacity-based retries, fallback routing,
    and call budget tracking.
    """
    def __init__(self, budget_tracker: Optional[CallBudgetTracker] = None):
        # Initialize budget tracker
        if budget_tracker is None:
            max_calls = int(os.getenv("TOTAL_CALL_BUDGET", "150"))
            self.budget_tracker = CallBudgetTracker(max_calls=max_calls)
        else:
            self.budget_tracker = budget_tracker

        # Load Provider Configurations
        # Check for multiple keys in GROQ_API_KEYS, or sequentially numbered GROQ_API_KEY_X, or fallback to GROQ_API_KEY
        keys_str = os.getenv("GROQ_API_KEYS", "")
        extracted_keys = [k.strip() for k in keys_str.split(",") if self._is_key_valid(k.strip())]
        
        # Also grab any keys defined as GROQ_API_KEY_1, GROQ_API_KEY_2, etc.
        for env_var in os.environ:
            if env_var.startswith("GROQ_API_KEY_"):
                val = os.getenv(env_var)
                if self._is_key_valid(val):
                    extracted_keys.append(val.strip())
                    
        # If still none, fallback to the base GROQ_API_KEY
        if not extracted_keys:
            base_key = os.getenv("GROQ_API_KEY", "")
            if self._is_key_valid(base_key):
                extracted_keys.append(base_key.strip())
                
        self.groq_keys = extracted_keys
        self.groq_model = os.getenv("GROQ_MODEL")
        self.groq_rpm = float(os.getenv("GROQ_RPM", "30"))
        self.groq_tpm = float(os.getenv("GROQ_TPM", "14400"))

        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL")
        self.openrouter_rpm = float(os.getenv("OPENROUTER_RPM", "10"))
        self.openrouter_tpm = float(os.getenv("OPENROUTER_TPM", "0"))  # 0 means disabled

        # Initialize Limiters
        self.groq_limiter = TokenBucketRateLimiter(max_rpm=self.groq_rpm, max_tpm=self.groq_tpm)
        self.openrouter_limiter = TokenBucketRateLimiter(max_rpm=self.openrouter_rpm, max_tpm=self.openrouter_tpm)

        # Initialize clients if valid keys are present
        self.groq_clients = []
        if self.groq_keys and self.groq_model:
            for key in self.groq_keys:
                client = AsyncOpenAI(
                    api_key=key,
                    base_url="https://api.groq.com/openai/v1"
                )
                self.groq_clients.append(client)
            logger.info(f"Initialized {len(self.groq_clients)} Groq client(s) for round-robin/fallback.")
        else:
            logger.warning("No valid Groq API keys provided.")

        self.openrouter_client = None
        if self._is_key_valid(self.openrouter_key) and self.openrouter_model:
            self.openrouter_client = AsyncOpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("OpenRouter client initialized successfully.")
        else:
            logger.warning("OpenRouter API key not provided or is placeholder.")

    def _is_key_valid(self, api_key: str) -> bool:
        """Helper to check if API key is set and not a placeholder."""
        if not api_key:
            return False
        normalized = api_key.strip().upper()
        if "PLACEHOLDER" in normalized or "YOUR_" in normalized:
            return False
        return True

    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Creates a chat completion using the primary provider (Groq),
        falling back to OpenRouter if Groq fails or is not configured.
        """
        # Always check budget first
        self.budget_tracker.check_budget()

        if not hasattr(self, 'current_groq_index'):
            self.current_groq_index = 0

        last_exception = None

        # 1. Try Groq Clients starting from the current active index
        while self.groq_clients and self.current_groq_index < len(self.groq_clients):
            client = self.groq_clients[self.current_groq_index]
            name = f"groq_key_{self.current_groq_index + 1}"
            model = self.groq_model
            limiter = self.groq_limiter

            logger.info(f"Attempting completion with provider: {name}, model: {model}")
            try:
                # Wrap with Tenacity ONLY for connection/timeout errors
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    retry=retry_if_exception_type((
                        openai.APIConnectionError,
                        openai.APITimeoutError
                    )),
                    reraise=True
                ):
                    with attempt:
                        total_input_chars = sum(len(m.get("content", "")) for m in messages)
                        estimated_tokens = int(total_input_chars / 4) + (max_tokens or 500)
                        
                        await limiter.acquire(estimated_tokens=estimated_tokens)

                        response = await client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                        
                        usage = response.usage
                        input_tokens = usage.prompt_tokens if usage else int(total_input_chars / 4)
                        output_tokens = usage.completion_tokens if usage else (max_tokens or 100)
                        actual_total_tokens = input_tokens + output_tokens

                        await limiter.update_tokens(actual_total_tokens)
                        
                        self.budget_tracker.record_call(
                            provider=name,
                            model=model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens
                        )
                        
                        logger.info(f"Completion successful via {name}.")
                        return {
                            "provider": name,
                            "model": model,
                            "content": response.choices[0].message.content,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens
                        }
            except openai.RateLimitError as e:
                logger.warning(f"Provider {name} hit Rate Limit (429): {e}. Moving to next Groq key...")
                last_exception = e
                self.current_groq_index += 1  # Permanently switch to the next key
            except Exception as e:
                logger.error(f"Provider {name} failed: {e}")
                last_exception = e
                self.current_groq_index += 1  # Move to next key on unexpected errors too

        # 2. If all Groq keys are exhausted, fallback to OpenRouter
        if self.openrouter_client:
            name = "openrouter"
            client = self.openrouter_client
            model = self.openrouter_model
            limiter = self.openrouter_limiter

            logger.info(f"Attempting completion with fallback provider: {name}, model: {model}")
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    retry=retry_if_exception_type((
                        openai.RateLimitError,
                        openai.APIConnectionError,
                        openai.APITimeoutError
                    )),
                    reraise=True
                ):
                    with attempt:
                        total_input_chars = sum(len(m.get("content", "")) for m in messages)
                        estimated_tokens = int(total_input_chars / 4) + (max_tokens or 500)
                        await limiter.acquire(estimated_tokens=estimated_tokens)

                        response = await client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                        
                        usage = response.usage
                        input_tokens = usage.prompt_tokens if usage else int(total_input_chars / 4)
                        output_tokens = usage.completion_tokens if usage else (max_tokens or 100)
                        actual_total_tokens = input_tokens + output_tokens

                        await limiter.update_tokens(actual_total_tokens)
                        
                        self.budget_tracker.record_call(
                            provider=name,
                            model=model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens
                        )
                        
                        logger.info(f"Completion successful via {name}.")
                        return {
                            "provider": name,
                            "model": model,
                            "content": response.choices[0].message.content,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens
                        }
            except Exception as e:
                logger.error(f"Provider {name} failed: {e}")
                last_exception = e

        # If we got here, all providers failed
        raise last_exception or RuntimeError("All API providers failed.")
