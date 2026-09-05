import sys, os, json
sys.path.append(os.path.abspath('.'))
from src.sandbox import Sandbox

sb = Sandbox(timeout_seconds=5)
data = json.load(open('data/train_problems.json'))

p6 = data[5]
p7 = data[6]

p6_code = """
def climb_stairs(n: int) -> int:
    if n < 0:
        return n
    if n == 0:
        return 0
    if n == 1:
        return 1
    if n == 2:
        return 2
    a, b = 1, 2
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b
"""

p7_code = """
def is_valid(s: str) -> bool:
    for char in s:
        if char not in '()[]{}':
            return False
    stack = []
    mapping = {")": "(", "}": "{", "]": "["}
    for char in s:
        if char in mapping:
            top_element = stack.pop() if stack else '#'
            if mapping[char] != top_element:
                return False
        else:
            stack.append(char)
    return not stack
"""

print("=== Testing Problem 6 ===")
res6 = sb.run(p6_code, p6['tests'], language="Python")
print(f"Passed: {res6['passed_tests']}/{res6['total_tests']}")
if res6['passed_tests'] != res6['total_tests']:
    for o in res6['test_outputs']:
        if o['status'] != 'pass':
            print(f"  Test {o['id']}: {o['status']} actual={o.get('actual')} expected={o.get('expected')} input={o.get('input')}")

print("\n=== Testing Problem 7 ===")
res7 = sb.run(p7_code, p7['tests'], language="Python")
print(f"Passed: {res7['passed_tests']}/{res7['total_tests']}")
if res7['passed_tests'] != res7['total_tests']:
    for o in res7['test_outputs']:
        if o['status'] != 'pass':
            print(f"  Test {o['id']}: {o['status']} actual={o.get('actual')} expected={o.get('expected')} input={o.get('input')}")
