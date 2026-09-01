import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
import openai
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.rate_limiter import TokenBucketRateLimiter
from src.budget_tracker import CallBudgetTracker, BudgetExceededError

# Setup logging
logger = logging.getLogger(__name__)

# Resolve the project root relative to this file to load the .env file
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path, override=True)


class EvoClient:
    """
    EvoClient handles calling LLM APIs asynchronously with a 3-tier fallback chain:

        Tier 1: Ollama Local (unlimited, no rate limits, completely local)
        Tier 2: Groq Cloud (4 rotating API keys — fast fallback)
        Tier 3: OpenRouter Cloud (cloud safety net)

    Built-in features: rate-limiting, tenacity-based retries, round-robin key
    rotation, and call budget tracking.
    """

    def __init__(self, budget_tracker: Optional[CallBudgetTracker] = None):
        # ── Budget Tracker ────────────────────────────────────────────────────
        if budget_tracker is None:
            max_calls = int(os.getenv("TOTAL_CALL_BUDGET", "9999"))
            self.budget_tracker = CallBudgetTracker(max_calls=max_calls)
        else:
            self.budget_tracker = budget_tracker

        # ── Tier 1: Ollama Local ──────────────────────────────────────────────
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "")

        self.ollama_client = None
        if self.ollama_model:
            self.ollama_client = AsyncOpenAI(
                api_key="ollama",       # Ollama doesn't need a real API key
                base_url=self.ollama_base_url
            )
            logger.info(
                f"[Tier 1] Ollama Local: initialized → {self.ollama_base_url}, model={self.ollama_model}"
            )
        else:
            logger.warning("[Tier 1] Ollama: OLLAMA_MODEL not set, local fallback disabled.")

        # ── Tier 2: Groq ─────────────────────────────────────────────────────
        keys_str = os.getenv("GROQ_API_KEYS", "")
        extracted_keys = [k.strip() for k in keys_str.split(",") if self._is_key_valid(k.strip())]

        for env_var in os.environ:
            if env_var.startswith("GROQ_API_KEY_"):
                val = os.getenv(env_var)
                if self._is_key_valid(val):
                    extracted_keys.append(val.strip())

        if not extracted_keys:
            base_key = os.getenv("GROQ_API_KEY", "")
            if self._is_key_valid(base_key):
                extracted_keys.append(base_key.strip())

        self.groq_keys = extracted_keys
        self.groq_model = os.getenv("GROQ_MODEL")
        self.groq_rpm = float(os.getenv("GROQ_RPM", "30"))
        self.groq_tpm = float(os.getenv("GROQ_TPM", "14400"))
        self.groq_limiter = TokenBucketRateLimiter(max_rpm=self.groq_rpm, max_tpm=self.groq_tpm)

        self.groq_clients = []
        if self.groq_keys and self.groq_model:
            for key in self.groq_keys:
                client = AsyncOpenAI(
                    api_key=key,
                    base_url="https://api.groq.com/openai/v1"
                )
                self.groq_clients.append(client)
            logger.info(f"[Tier 2] Groq: {len(self.groq_clients)} key(s) loaded, model={self.groq_model}")
        else:
            logger.warning("[Tier 2] Groq: No valid API keys or model configured.")

        # ── Tier 3: OpenRouter ────────────────────────────────────────────────
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL")
        self.openrouter_rpm = float(os.getenv("OPENROUTER_RPM", "10"))
        self.openrouter_tpm = float(os.getenv("OPENROUTER_TPM", "0"))
        self.openrouter_limiter = TokenBucketRateLimiter(
            max_rpm=self.openrouter_rpm, max_tpm=self.openrouter_tpm
        )

        self.openrouter_client = None
        if self._is_key_valid(self.openrouter_key) and self.openrouter_model:
            self.openrouter_client = AsyncOpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info(f"[Tier 3] OpenRouter: initialized, model={self.openrouter_model}")
        else:
            logger.warning("[Tier 3] OpenRouter: No valid API key or model configured.")

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Creates a chat completion using the 3-tier fallback chain:
            Ollama Local → Groq (rotating keys) → OpenRouter
        """
        self.budget_tracker.check_budget()

        if not hasattr(self, "current_groq_index"):
            self.current_groq_index = 0

        last_exception = None
        total_input_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = int(total_input_chars / 4) + (max_tokens or 500)

        # ── Tier 1: Ollama Local (Primary) ─────────────────────────
        if self.ollama_client:
            logger.info(f"Attempting completion → Tier 1: Ollama Local (model={self.ollama_model})")
            try:
                response = await self.ollama_client.chat.completions.create(
                    model=self.ollama_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )

                if not getattr(response, "choices", None):
                    raise RuntimeError("Ollama returned empty choices.")

                # Ollama doesn't always return usage, so default gracefully
                usage = getattr(response, "usage", None)
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0

                self.budget_tracker.record_call(
                    provider="ollama_local",
                    model=self.ollama_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )

                logger.info(f"✓ Completion via Ollama Local (model={self.ollama_model})")
                return {
                    "provider": "ollama_local",
                    "model": self.ollama_model,
                    "content": response.choices[0].message.content,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }

            except Exception as e:
                logger.warning(f"Ollama Local failed: {e}. Falling back to Tier 2 (Groq)...")
                last_exception = e

        # ── Tier 2: Groq (round-robin across keys, 2 full passes) ────────────
        for groq_pass in range(2):
            while self.groq_clients and self.current_groq_index < len(self.groq_clients):
                client = self.groq_clients[self.current_groq_index]
                name = f"groq_key_{self.current_groq_index + 1}"

                logger.info(f"Attempting completion → Tier 2: {name} (model={self.groq_model})")
                try:
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(3),
                        wait=wait_exponential(multiplier=1, min=2, max=10),
                        retry=retry_if_exception_type((
                            RuntimeError,
                            openai.APIConnectionError,
                            openai.APITimeoutError
                        )),
                        reraise=True
                    ):
                        with attempt:
                            await self.groq_limiter.acquire(estimated_tokens=estimated_tokens)

                            response = await client.chat.completions.create(
                                model=self.groq_model,
                                messages=messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )

                            if not getattr(response, "choices", None):
                                raise RuntimeError(f"{name} returned empty choices.")

                            usage = response.usage
                            input_tokens = usage.prompt_tokens if usage else int(total_input_chars / 4)
                            output_tokens = usage.completion_tokens if usage else (max_tokens or 100)
                            await self.groq_limiter.update_tokens(input_tokens + output_tokens)

                            self.budget_tracker.record_call(
                                provider=name,
                                model=self.groq_model,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens
                            )

                            logger.info(f"✓ Completion via {name} ({input_tokens}+{output_tokens} tokens)")
                            return {
                                "provider": name,
                                "model": self.groq_model,
                                "content": response.choices[0].message.content,
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens
                            }

                except openai.RateLimitError as e:
                    logger.warning(f"{name} rate-limited (429). Rotating to next Groq key...")
                    last_exception = e
                    self.current_groq_index += 1
                except Exception as e:
                    logger.error(f"{name} failed: {e}")
                    last_exception = e
                    self.current_groq_index += 1

            if self.groq_clients and self.current_groq_index >= len(self.groq_clients) and groq_pass == 0:
                logger.info("All Groq keys exhausted on pass 1. Resetting index for pass 2...")
                self.current_groq_index = 0

        # ── Tier 3: OpenRouter ────────────────────────────────────────────────
        if self.openrouter_client:
            logger.info(f"Falling back → Tier 3: OpenRouter (model={self.openrouter_model})")
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    retry=retry_if_exception_type((
                        RuntimeError,
                        openai.RateLimitError,
                        openai.APIConnectionError,
                        openai.APITimeoutError
                    )),
                    reraise=True
                ):
                    with attempt:
                        await self.openrouter_limiter.acquire(estimated_tokens=estimated_tokens)

                        response = await self.openrouter_client.chat.completions.create(
                            model=self.openrouter_model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )

                        if not getattr(response, "choices", None):
                            raise RuntimeError("OpenRouter returned empty choices.")

                        usage = response.usage
                        input_tokens = usage.prompt_tokens if usage else int(total_input_chars / 4)
                        output_tokens = usage.completion_tokens if usage else (max_tokens or 100)
                        await self.openrouter_limiter.update_tokens(input_tokens + output_tokens)

                        self.budget_tracker.record_call(
                            provider="openrouter",
                            model=self.openrouter_model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens
                        )

                        logger.info(f"✓ Completion via OpenRouter ({input_tokens}+{output_tokens} tokens)")
                        return {
                            "provider": "openrouter",
                            "model": self.openrouter_model,
                            "content": response.choices[0].message.content,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens
                        }

            except Exception as e:
                logger.error(f"OpenRouter failed: {e}")
                last_exception = e

        # All 3 tiers failed
        raise last_exception or RuntimeError(
            "All API providers failed: Ollama Local, Groq (all keys), and OpenRouter."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _is_key_valid(self, api_key: str) -> bool:
        """Returns True if the API key is set and not a placeholder."""
        if not api_key:
            return False
        normalized = api_key.strip().upper()
        if "PLACEHOLDER" in normalized or "YOUR_" in normalized:
            return False
        return True
