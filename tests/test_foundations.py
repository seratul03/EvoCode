import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from evoflow.rate_limiter import TokenBucketRateLimiter
from evoflow.budget_tracker import CallBudgetTracker, BudgetExceededError
from evoflow.client import EvoClient
import openai

@pytest.mark.asyncio
async def test_rate_limiter_rpm():
    # 60 RPM = 1 request per second
    limiter = TokenBucketRateLimiter(max_rpm=60.0, max_tpm=0.0)
    
    # Force set to 1.0 token
    limiter.rpm_tokens = 1.0
    
    start_time = time.monotonic()
    # First acquire should be immediate
    await limiter.acquire()
    
    # Second acquire should wait ~1s because capacity is exhausted
    await limiter.acquire()
    end_time = time.monotonic()
    
    elapsed = end_time - start_time
    # Adding a small tolerance for system execution scheduling
    assert elapsed >= 0.85

@pytest.mark.asyncio
async def test_rate_limiter_tpm():
    # 6000 TPM = 100 tokens per second
    limiter = TokenBucketRateLimiter(max_rpm=0.0, max_tpm=6000.0)
    limiter.tpm_tokens = 10.0
    
    # Consume 20 tokens, pushing the balance to -10.0
    await limiter.update_tokens(20)
    assert -10.0 <= limiter.tpm_tokens <= -9.9
    
    start_time = time.monotonic()
    # Next acquire will block until the balance is >= 0
    # refilling 10 tokens at 100 tokens/sec takes 0.1 seconds
    await limiter.acquire()
    end_time = time.monotonic()
    
    elapsed = end_time - start_time
    assert elapsed >= 0.08

def test_budget_tracker():
    tracker = CallBudgetTracker(max_calls=2)
    tracker.record_call("groq", "llama3-70b-8192", 1000, 2000)
    
    # Price for groq/llama3-70b-8192:
    # Input: 1000 * 0.59 / 1,000,000 = $0.00059
    # Output: 2000 * 0.79 / 1,000,000 = $0.00158
    # Total: $0.00217
    summary = tracker.get_summary()
    assert summary["total_calls"] == 1
    assert summary["total_input_tokens"] == 1000
    assert summary["total_output_tokens"] == 2000
    assert abs(summary["total_cost"] - 0.00217) < 1e-6
    
    # Second call
    tracker.record_call("groq", "llama3-70b-8192", 1000, 2000)
    assert tracker.get_summary()["total_calls"] == 2
    
    # Third call should raise BudgetExceededError
    with pytest.raises(BudgetExceededError):
        tracker.record_call("groq", "llama3-70b-8192", 1000, 2000)
        
    with pytest.raises(BudgetExceededError):
        tracker.check_budget()

@pytest.mark.asyncio
async def test_client_fallback_success():
    """Verify that if Groq fails, EvoClient falls back to OpenRouter."""
    with patch("evoflow.client.AsyncOpenAI") as MockOpenAI:
        # Create mock completions
        mock_groq_chat = MagicMock()
        mock_groq_chat.completions.create = AsyncMock(side_effect=openai.APIConnectionError(
            message="Groq connection failed", request=MagicMock()
        ))
        
        mock_or_chat = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from OpenRouter!"
        mock_or_chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[mock_choice],
            usage=MagicMock(prompt_tokens=50, completion_tokens=150)
        ))

        # Mock the instantiation of clients
        def client_side_effect(api_key, base_url):
            mock = MagicMock()
            if "groq" in base_url:
                mock.chat = mock_groq_chat
            else:
                mock.chat = mock_or_chat
            return mock

        MockOpenAI.side_effect = client_side_effect

        with patch.dict("os.environ", {
            "GROQ_API_KEY": "groq_valid_test_key",
            "OPENROUTER_API_KEY": "openrouter_valid_test_key"
        }):
            client = EvoClient()
            res = await client.create_completion([{"role": "user", "content": "hi"}])
            
            assert res["provider"] == "openrouter"
            assert res["content"] == "Hello from OpenRouter!"
            assert res["input_tokens"] == 50
            assert res["output_tokens"] == 150
            
            # Check budget counts
            summary = client.budget_tracker.get_summary()
            assert summary["total_calls"] == 1
            assert summary["usage_by_model"]["openrouter/meta-llama/llama-3-70b-instruct:free"]["calls"] == 1
