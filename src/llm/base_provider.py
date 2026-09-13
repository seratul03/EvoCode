from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.budget_tracker import CallBudgetTracker

class BaseProvider(ABC):
    def __init__(self, budget_tracker: CallBudgetTracker):
        self.budget_tracker = budget_tracker

    @abstractmethod
    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        estimated_tokens: int = 0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Creates a chat completion.
        Returns a dict with:
          - provider: str
          - model: str
          - content: str
          - input_tokens: int
          - output_tokens: int
        Raises an exception if the provider fails.
        """
        pass
