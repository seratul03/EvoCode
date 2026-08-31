import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding='utf-8')

from src.client import EvoClient

async def test_api():
    print("Initializing EvoClient...")
    try:
        client = EvoClient()
        print(f"Groq Keys Loaded: {len(client.groq_keys)}")
        print(f"Groq Model: {client.groq_model}")
        print(f"OpenRouter Model: {client.openrouter_model}")
        
        messages = [
            {"role": "system", "content": "You are a helpful Python code assistant."},
            {"role": "user", "content": "Write a python function `add(a, b)` that returns `a + b`."}
        ]
        
        print("\nSending API completion request...")
        response = await client.create_completion(messages=messages, temperature=0.2, max_tokens=100)
        
        print("\n[SUCCESS] API Response Received!")
        print(f"Provider: {response.get('provider')}")
        print(f"Model: {response.get('model')}")
        print(f"Input Tokens: {response.get('input_tokens')}")
        print(f"Output Tokens: {response.get('output_tokens')}")
        print(f"Content snippet:\n{response.get('content')}")
        
    except Exception as e:
        print(f"\n[FAILURE] API Call Failed with Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api())
