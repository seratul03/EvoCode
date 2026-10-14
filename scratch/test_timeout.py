import asyncio
import time
from src.sandbox import Sandbox

async def main():
    sandbox = Sandbox(timeout_seconds=5)
    code = """
def divide(dividend: int, divisor: int) -> int:
    # infinite loop
    while True:
        pass
"""
    test_cases = [{"id": 1, "input": "10, 3", "expected": "3"}]
    test_cases = [{"id": 1, "input": "divide(10, 3)", "expected": "3"}]
    
    print("Running sandbox...")
    start = time.time()
    results = sandbox.run(code, test_cases)
    end = time.time()
    print(f"Sandbox returned after {end - start:.2f} seconds")
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
