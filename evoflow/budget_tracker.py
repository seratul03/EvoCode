import threading
from typing import Dict, Any

class BudgetExceededError(Exception):
    """Raised when the maximum LLM call budget is exceeded."""
    pass

class CallBudgetTracker:
    """
    Tracks LLM calls, token usage, and simulated monetary cost.
    Enforces a strict global limit on the number of LLM calls.
    """
    def __init__(self, max_calls: int = 150):
        self.max_calls = max_calls
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        
        # Details grouped by provider and model
        # Structure: { "provider/model": { "calls": int, "input_tokens": int, "output_tokens": int, "cost": float } }
        self.usage_by_model: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def check_budget(self):
        """Raises BudgetExceededError if the call count limit is reached."""
        with self.lock:
            if self.total_calls >= self.max_calls:
                raise BudgetExceededError(
                    f"LLM call budget limit reached: {self.total_calls}/{self.max_calls} calls used."
                )

    def record_call(self, provider: str, model: str, input_tokens: int, output_tokens: int):
        """
        Record a successful LLM call, updating counts, token usage, and cost estimation.
        """
        with self.lock:
            # Although we check_budget before starting the call, we also assert here.
            if self.total_calls >= self.max_calls:
                raise BudgetExceededError(
                    f"Failed to record call. Budget already exceeded: {self.total_calls}/{self.max_calls}"
                )
                
            self.total_calls += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            
            # Calculate cost based on provider/model rates
            cost = self._calculate_cost(provider, model, input_tokens, output_tokens)
            self.total_cost += cost
            
            key = f"{provider.lower()}/{model.lower()}"
            if key not in self.usage_by_model:
                self.usage_by_model[key] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0
                }
            self.usage_by_model[key]["calls"] += 1
            self.usage_by_model[key]["input_tokens"] += input_tokens
            self.usage_by_model[key]["output_tokens"] += output_tokens
            self.usage_by_model[key]["cost"] += cost

    def _calculate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculates estimated cost per million tokens."""
        # Simple pricing dictionary (input cost / 1M tokens, output cost / 1M tokens)
        prices = {
            "groq": {
                "llama3-70b-8192": (0.59, 0.79),
                "llama3-8b-8192": (0.05, 0.08),
                "mixtral-8x7b-32768": (0.24, 0.24),
                "llama-3.1-70b-versatile": (0.59, 0.79),
                "llama-3.1-8b-instant": (0.05, 0.08),
                "openai/gpt-oss-20b": (0.59, 0.79),
            },
            "openrouter": {
                # OpenRouter free tier models are $0
                "meta-llama/llama-3-70b-instruct:free": (0.0, 0.0),
                "meta-llama/llama-3-8b-instruct:free": (0.0, 0.0),
            }
        }
        
        provider_prices = prices.get(provider.lower(), {})
        # Find exact model or default to 0.0
        model_prices = provider_prices.get(model.lower(), (0.0, 0.0))
        input_price_per_1m, output_price_per_1m = model_prices
        
        cost = (input_tokens * input_price_per_1m + output_tokens * output_price_per_1m) / 1_000_000.0
        return cost

    def get_summary(self) -> Dict[str, Any]:
        """Returns a snapshot of the usage stats."""
        with self.lock:
            return {
                "total_calls": self.total_calls,
                "max_calls": self.max_calls,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cost": round(self.total_cost, 6),
                "usage_by_model": {k: dict(v) for k, v in self.usage_by_model.items()}
            }
