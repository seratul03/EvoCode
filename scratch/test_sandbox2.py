import sys, os
sys.path.append(os.path.abspath('.'))
from src.sandbox import Sandbox

sb = Sandbox(timeout_seconds=10)

# Test MinStack (class-based, script mode)
minstack_code = """
class MinStack:
    def __init__(self):
        self.stack = []
        self.min_stack = []
    def push(self, val):
        self.stack.append(val)
        self.min_stack.append(min(val, self.min_stack[-1] if self.min_stack else val))
    def pop(self):
        self.stack.pop()
        self.min_stack.pop()
    def top(self):
        return self.stack[-1]
    def get_min(self):
        return self.min_stack[-1]
"""

minstack_tests = [
    {"id": 0, "input": "ms = MinStack(); ms.push(3); ms.push(5); str(ms.get_min()) + ',' + str(ms.top())", "expected": "3,5"},
    {"id": 1, "input": "ms = MinStack(); ms.push(-2); ms.push(0); ms.push(-3); str(ms.get_min())", "expected": "-3"},
    {"id": 2, "input": "ms = MinStack(); ms.push(-2); ms.push(0); ms.push(-3); ms.pop(); str(ms.get_min())", "expected": "-2"},
]

print("=== Testing MinStack (script mode) ===")
res = sb.run(minstack_code, minstack_tests, language="Python")
print(f"Passed: {res['passed_tests']}/{res['total_tests']}")
for o in res['test_outputs']:
    print(f"  Test {o['id']}: {o['status']}", o.get('error', o.get('actual', '')))

# Test LRU Cache (class-based, script mode)
lru_code = """
from collections import OrderedDict
class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.cache = OrderedDict()
    def get(self, key):
        if key not in self.cache: return -1
        self.cache.move_to_end(key)
        return self.cache[key]
    def put(self, key, value):
        if key in self.cache: self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.cap:
            self.cache.popitem(last=False)
"""

lru_tests = [
    {"id": 0, "input": "c = LRUCache(2); c.put(1,1); c.put(2,2); str(c.get(1))", "expected": "1"},
    {"id": 1, "input": "c = LRUCache(2); c.put(1,1); c.put(2,2); c.put(3,3); str(c.get(2))", "expected": "2"},
    {"id": 2, "input": "c = LRUCache(2); c.put(1,1); c.put(2,2); c.get(1); c.put(3,3); str(c.get(2))", "expected": "-1"},
]

print("\n=== Testing LRU Cache (script mode) ===")
res2 = sb.run(lru_code, lru_tests, language="Python")
print(f"Passed: {res2['passed_tests']}/{res2['total_tests']}")
for o in res2['test_outputs']:
    print(f"  Test {o['id']}: {o['status']}", o.get('error', o.get('actual', '')))

# Test Two-Sum (function mode, still works)
twosum_code = """
from typing import List
def solve(nums: List[int], target: int) -> List[int]:
    m = {}
    for i, v in enumerate(nums):
        if target - v in m:
            return [m[target - v], i]
        m[v] = i
    return []
"""
twosum_tests = [
    {"id": 0, "input": "solve([2,7,11,15], 9)", "expected": "[0, 1]"},
    {"id": 1, "input": "solve([3,2,4], 6)", "expected": "[1, 2]"},
]

print("\n=== Testing Two Sum (function mode) ===")
res3 = sb.run(twosum_code, twosum_tests, language="Python")
print(f"Passed: {res3['passed_tests']}/{res3['total_tests']}")
for o in res3['test_outputs']:
    print(f"  Test {o['id']}: {o['status']}", o.get('error', o.get('actual', '')))
