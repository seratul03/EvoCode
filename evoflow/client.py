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
        self.groq_key = os.getenv("GROQ_API_KEY", "")
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
        self.groq_client = None
        if self._is_key_valid(self.groq_key) and self.groq_model:
            self.groq_client = AsyncOpenAI(
                api_key=self.groq_key,
                base_url="https://api.groq.com/openai/v1"
            )
            logger.info("Groq client initialized successfully.")
        else:
            logger.warning("Groq API key not provided or is placeholder.")

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

        # Determine which providers are viable
        providers = []
        if self.groq_client:
            providers.append({
                "name": "groq",
                "client": self.groq_client,
                "model": self.groq_model,
                "limiter": self.groq_limiter
            })
        if self.openrouter_client:
            providers.append({
                "name": "openrouter",
                "client": self.openrouter_client,
                "model": self.openrouter_model,
                "limiter": self.openrouter_limiter
            })

        if not providers:
            raise ValueError("No valid API keys configured. Please update your .env file.")

        last_exception = None
        for provider_info in providers:
            name = provider_info["name"]
            client = provider_info["client"]
            model = provider_info["model"]
            limiter = provider_info["limiter"]

            logger.info(f"Attempting completion with provider: {name}, model: {model}")
            try:
                # Wrap with Tenacity retry logic
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
                        # Estimate request size (input characters / 4 + max_tokens)
                        total_input_chars = sum(len(m.get("content", "")) for m in messages)
                        estimated_tokens = int(total_input_chars / 4) + (max_tokens or 500)
                        
                        # Acquire token bucket permission
                        await limiter.acquire(estimated_tokens=estimated_tokens)

                        response = await client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                        
                        # Extract usage details
                        usage = response.usage
                        input_tokens = usage.prompt_tokens if usage else int(total_input_chars / 4)
                        output_tokens = usage.completion_tokens if usage else (max_tokens or 100)
                        actual_total_tokens = input_tokens + output_tokens

                        # Update rate limiter with actual consumed tokens
                        await limiter.update_tokens(actual_total_tokens)
                        
                        # Update global budget tracker
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
                # Fall through to the next provider in the list

        # If we got here, all providers failed
        raise last_exception or RuntimeError("All API providers failed.")
