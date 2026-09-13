import os
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from src.llm.base_provider import BaseProvider
from src.budget_tracker import CallBudgetTracker

logger = logging.getLogger(__name__)

class OllamaProvider(BaseProvider):
    def __init__(self, budget_tracker: CallBudgetTracker):
        super().__init__(budget_tracker)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model = os.getenv("OLLAMA_MODEL", "")
        
        self.client = None
        if self.model:
            self.client = AsyncOpenAI(
                api_key="ollama",
                base_url=self.base_url
            )
            logger.info(f"[Tier 1] Ollama Local: initialized → {self.base_url}, model={self.model}")
        else:
            logger.warning("[Tier 1] Ollama: OLLAMA_MODEL not set, local primary disabled.")

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
        if not self.client:
            raise RuntimeError("Ollama provider is not enabled.")

        logger.info(f"Attempting completion → Tier 1: Ollama Local (model={self.model})")
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        if not getattr(response, "choices", None):
            raise RuntimeError("Ollama returned empty choices.")

        usage = getattr(response, "usage", None)
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        self.budget_tracker.record_call(
            provider="ollama_local",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

        logger.info(f"✓ Completion via Ollama Local (model={self.model})")
        return {
            "provider": "ollama_local",
            "model": self.model,
            "content": response.choices[0].message.content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
