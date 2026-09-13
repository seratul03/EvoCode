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

class OpenRouterProvider(BaseProvider):
    def __init__(self, budget_tracker: CallBudgetTracker):
        super().__init__(budget_tracker)
        
        self.key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("OPENROUTER_MODEL")
        self.rpm = float(os.getenv("OPENROUTER_RPM", "10"))
        self.tpm = float(os.getenv("OPENROUTER_TPM", "0"))
        self.limiter = TokenBucketRateLimiter(
            max_rpm=self.rpm, max_tpm=self.tpm
        )

        self.client = None
        if self._is_key_valid(self.key) and self.model:
            self.client = AsyncOpenAI(
                api_key=self.key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info(f"[Tier 3] OpenRouter: initialized, model={self.model}")
        else:
            logger.warning("[Tier 3] OpenRouter: No valid API key or model configured.")

    def _is_key_valid(self, api_key: str) -> bool:
        if not api_key:
            return False
        normalized = api_key.strip().upper()
        if "PLACEHOLDER" in normalized or "YOUR_" in normalized:
            return False
        return True

    @property
    def is_enabled(self) -> bool:
        return self.client is not None

    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        estimated_tokens: int = 0,
        **kwargs
    ) -> Dict[str, Any]:
        if not self.is_enabled:
            raise RuntimeError("OpenRouter provider is not enabled.")

        logger.info(f"Falling back → Tier 3: OpenRouter (model={self.model})")
        last_exception = None
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
                    await self.limiter.acquire(estimated_tokens=estimated_tokens)

                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )

                    if not getattr(response, "choices", None):
                        raise RuntimeError("OpenRouter returned empty choices.")

                    usage = response.usage
                    total_input_chars = sum(len(m.get("content", "")) for m in messages)
                    input_tokens = usage.prompt_tokens if usage else int(total_input_chars / 4)
                    output_tokens = usage.completion_tokens if usage else (max_tokens or 100)
                    await self.limiter.update_tokens(input_tokens + output_tokens)

                    self.budget_tracker.record_call(
                        provider="openrouter",
                        model=self.model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens
                    )

                    logger.info(f"✓ Completion via OpenRouter ({input_tokens}+{output_tokens} tokens)")
                    return {
                        "provider": "openrouter",
                        "model": self.model,
                        "content": response.choices[0].message.content,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens
                    }

        except Exception as e:
            logger.error(f"OpenRouter failed: {e}")
            last_exception = e

        raise last_exception or RuntimeError("OpenRouter provider failed.")
