import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from src.budget_tracker import CallBudgetTracker
from src.llm.ollama_provider import OllamaProvider
from src.llm.groq_provider import GroqProvider
from src.llm.openrouter_provider import OpenRouterProvider

# Setup logging
logger = logging.getLogger(__name__)

# Resolve the project root relative to this file to load the .env file
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path, override=True)


class EvoClient:
    """
    EvoClient handles calling LLM APIs asynchronously with a 3-tier fallback chain:

        Tier 1: Ollama Local (unlimited, no rate limits, completely local primary)
        Tier 2: Groq Cloud (rotating API keys — fast fallback)
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

        # ── Providers ────────────────────────────────────────────────────────
        self.ollama = OllamaProvider(self.budget_tracker)
        self.groq = GroqProvider(self.budget_tracker)
        self.openrouter = OpenRouterProvider(self.budget_tracker)

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

        total_input_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = int(total_input_chars / 4) + (max_tokens or 500)
        last_exception = None

        # ── Tier 1: Ollama Local (Primary) ─────────────────────────
        if self.ollama.is_enabled:
            try:
                return await self.ollama.create_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    estimated_tokens=estimated_tokens,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Ollama Local failed: {e}. Falling back to Tier 2 (Groq)...")
                last_exception = e

        # ── Tier 2: Groq (round-robin across keys) ───────────────────────────
        if self.groq.is_enabled:
            try:
                return await self.groq.create_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    estimated_tokens=estimated_tokens,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Groq failed: {e}. Falling back to Tier 3 (OpenRouter)...")
                last_exception = e

        # ── Tier 3: OpenRouter ────────────────────────────────────────────────
        if self.openrouter.is_enabled:
            try:
                return await self.openrouter.create_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    estimated_tokens=estimated_tokens,
                    **kwargs
                )
            except Exception as e:
                logger.error(f"OpenRouter failed: {e}")
                last_exception = e

        # All 3 tiers failed
        raise last_exception or RuntimeError(
            "All API providers failed: Ollama Local, Groq (all keys), and OpenRouter."
        )
