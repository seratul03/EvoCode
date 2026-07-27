import asyncio
import os
import sys
from dotenv import load_dotenv

# Resolve project root and insert into sys.path to enable relative imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from evoflow.client import EvoClient
from evoflow.budget_tracker import CallBudgetTracker

async def run_demo():
    print("=" * 60)
    print("EVOCODE DAYS 1-2 FOUNDATIONS DEMO")
    print("=" * 60)
    
    # Initialize client
    client = EvoClient()
    
    has_groq = client._is_key_valid(client.groq_key)
    has_or = client._is_key_valid(client.openrouter_key)
    
    print(f"Groq API Key Configured: {has_groq} (Model: {client.groq_model})")
    print(f"OpenRouter API Key Configured: {has_or} (Model: {client.openrouter_model})")
    
    # If no keys are configured, set up dummy/mock clients to demonstrate the framework functionality
    if not (has_groq or has_or):
        print("\n[NOTE] No real API keys found. Running in SIMULATED mode.")
        print("To run for real, update the keys in your local '.env' file.")
        
        # We will mock the client completion to simulate a successful run
        from unittest.mock import AsyncMock, MagicMock
        import openai
        
        # Mock Groq client to raise a connection/rate-limit error (to demonstrate retry/fallback)
        client.groq_client = AsyncMock()
        client.groq_client.chat.completions.create.side_effect = openai.APIConnectionError(
            message="Simulated Groq Connection Error", request=MagicMock()
        )
        
        # Mock OpenRouter client to succeed
        client.openrouter_client = AsyncMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Simulated response: Fix the bug by adding a bounds check to 'list_dir'."
        client.openrouter_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice],
            usage=MagicMock(prompt_tokens=450, completion_tokens=150)
        )
        
    print("\nExecuting concurrent requests (verifying concurrency, fallback, and tracking)...")
    
    messages = [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": "Fix the out-of-bounds error in python list index."}
    ]
    
    # Run 3 concurrent requests
    tasks = [client.create_completion(messages, temperature=0.2) for _ in range(3)]
    
    print("Dispatched 3 requests concurrently...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\nResults:")
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            print(f" Request {i+1}: Failed with error: {res}")
        else:
            print(f" Request {i+1}: Succeeded via {res['provider'].upper()}")
            print(f"   Content: {res['content']}")
            print(f"   Tokens: Input {res['input_tokens']}, Output {res['output_tokens']}")
            
    print("\n" + "=" * 60)
    print("BUDGET & USAGE SUMMARY")
    print("=" * 60)
    summary = client.budget_tracker.get_summary()
    print(f"Total Calls Made: {summary['total_calls']} / {summary['max_calls']}")
    print(f"Total Input Tokens: {summary['total_input_tokens']}")
    print(f"Total Output Tokens: {summary['total_output_tokens']}")
    print(f"Total Cost (USD): ${summary['total_cost']:.6f}")
    print("\nBreakdown by Model:")
    for model_key, details in summary["usage_by_model"].items():
        print(f"  - {model_key}: {details['calls']} calls, {details['input_tokens']} in, {details['output_tokens']} out, ${details['cost']:.6f}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_demo())
