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
    # Wait, ast.parse("10, 3", mode='eval') yields a Tuple.
    # The parsing logic in _parse_tests_to_json:
    # node = ast.parse(inp, mode='eval')
    # args = [ast.literal_eval(arg) for arg in node.body.args] if it is a call? No, node.body is a Tuple if we pass "10, 3". Tuple doesn't have `.args`!
    # Ah, the _parse_tests_to_json uses `node.body.args`, which only exists if it's a Call object. Wait, let's see how `input` is formatted.
    test_cases = [{"id": 1, "input": "divide(10, 3)", "expected": "3"}]
    
    print("Running sandbox...")
    start = time.time()
    results = sandbox.run(code, test_cases)
    end = time.time()
    print(f"Sandbox returned after {end - start:.2f} seconds")
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
