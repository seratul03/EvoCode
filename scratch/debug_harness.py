"""
Dumps the actual files that sandbox.py would write to disk, 
so we can inspect them before running Docker.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.sandbox import Sandbox

sb = Sandbox()

test_cases = [
    {"id": 1, "input": "3, 5", "expected": "8"},
    {"id": 2, "input": "-2, 10", "expected": "8"},
]

java_code = """public class Solution {
    public int sum(int a, int b) {
        return a + b;
    }
}"""

cpp_code = """int sum(int a, int b) {
    return a + b;
}"""

java_full = sb._build_java_harness(java_code, test_cases)
cpp_full  = sb._build_cpp_harness(cpp_code, test_cases)

print("=" * 60)
print("JAVA FILE:")
print("=" * 60)
print(java_full)

print()
print("=" * 60)
print("CPP FILE:")
print("=" * 60)
print(cpp_full)
