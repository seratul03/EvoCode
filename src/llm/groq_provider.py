import os
import logging
from typing import List, Dict, Any, Optional
import openai
from openai import AsyncOpenAI
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.llm.base_provider import BaseProvider
from src.budget_tracker import CallBudgetTracker
from src.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

class GroqProvider(BaseProvider):
    def __init__(self, budget_tracker: CallBudgetTracker):
        super().__init__(budget_tracker)
        
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

        self.keys = extracted_keys
        self.model = os.getenv("GROQ_MODEL")
        self.rpm = float(os.getenv("GROQ_RPM", "30"))
        self.tpm = float(os.getenv("GROQ_TPM", "14400"))
        self.limiter = TokenBucketRateLimiter(max_rpm=self.rpm, max_tpm=self.tpm)

        self.clients = []
        if self.keys and self.model:
            for key in self.keys:
                client = AsyncOpenAI(
                    api_key=key,
                    base_url="https://api.groq.com/openai/v1"
                )
                self.clients.append(client)
            logger.info(f"[Tier 2] Groq: {len(self.clients)} key(s) loaded, model={self.model}")
        else:
            logger.warning("[Tier 2] Groq: No valid API keys or model configured.")
            
        self.current_index = 0

    def _is_key_valid(self, api_key: str) -> bool:
        if not api_key:
            return False
        normalized = api_key.strip().upper()
        if "PLACEHOLDER" in normalized or "YOUR_" in normalized:
            return False
        return True

    @property
    def is_enabled(self) -> bool:
        return len(self.clients) > 0

    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        estimated_tokens: int = 0,
        **kwargs
    ) -> Dict[str, Any]:
        if not self.is_enabled:
            raise RuntimeError("Groq provider is not enabled.")

        last_exception = None
        for groq_pass in range(2):
            while self.clients and self.current_index < len(self.clients):
                client = self.clients[self.current_index]
                name = f"groq_key_{self.current_index + 1}"

                logger.info(f"Attempting completion → Tier 2: {name} (model={self.model})")
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
                            await self.limiter.acquire(estimated_tokens=estimated_tokens)

                            response = await client.chat.completions.create(
                                model=self.model,
                                messages=messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )

                            if not getattr(response, "choices", None):
                                raise RuntimeError(f"{name} returned empty choices.")

                            usage = response.usage
                            total_input_chars = sum(len(m.get("content", "")) for m in messages)
                            input_tokens = usage.prompt_tokens if usage else int(total_input_chars / 4)
                            output_tokens = usage.completion_tokens if usage else (max_tokens or 100)
                            await self.limiter.update_tokens(input_tokens + output_tokens)

                            self.budget_tracker.record_call(
                                provider=name,
                                model=self.model,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens
                            )

                            logger.info(f"✓ Completion via {name} ({input_tokens}+{output_tokens} tokens)")
                            return {
                                "provider": name,
                                "model": self.model,
                                "content": response.choices[0].message.content,
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens
                            }

                except openai.RateLimitError as e:
                    logger.warning(f"{name} rate-limited (429). Rotating to next Groq key...")
                    last_exception = e
                    self.current_index += 1
                except Exception as e:
                    logger.error(f"{name} failed: {e}")
                    last_exception = e
                    self.current_index += 1

            if self.clients and self.current_index >= len(self.clients) and groq_pass == 0:
                logger.info("All Groq keys exhausted on pass 1. Resetting index for pass 2...")
                self.current_index = 0

        raise last_exception or RuntimeError("All Groq keys failed.")
