import sys
import os

# Add src to path so we can import sandbox
sys.path.append(os.path.abspath('src'))
from sandbox import Sandbox

sb = Sandbox(timeout_seconds=5)
code = """from typing import List
def solve(nums: List[int], target: int) -> List[int]:
    num_to_index = {}
    for i, num in enumerate(nums):
        if target - num in num_to_index:
            return [num_to_index[target - num], i]
        num_to_index[num] = i
    return []
"""
tests = [{"id": 1, "input": "([2,7,11,15], 9)", "expected": "[0, 1]"}]
res = sb.run(code, tests, language="Python")
print("Results:", res)
