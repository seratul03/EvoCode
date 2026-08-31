import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from src.fitness_scorer import FitnessScorer
from src.genome import EvaluatorGenome

scorer = FitnessScorer()
genome = EvaluatorGenome()

# Test 1: 0/20 tests - must be 0.0
tr_zero = {'passed_tests': 0, 'total_tests': 20, 'failed_test_ids': list(range(20)),
           'timeout_tests': [], 'crash_tests': [], 'execution_time_ms': 50, 'peak_memory_kb': 0}
r = scorer.calculate_fitness('def f(x): return x + 1', tr_zero, genome)
val = r["fitness_value"]
print(f"Test 1 (0/20 passed)  -> fitness={val}  {'PASS' if val == 0.0 else 'FAIL'}")

# Test 2: 20/20 tests - must be > 0
tr_full = {'passed_tests': 20, 'total_tests': 20, 'failed_test_ids': [],
           'timeout_tests': [], 'crash_tests': [], 'execution_time_ms': 80, 'peak_memory_kb': 512}
r2 = scorer.calculate_fitness('def f(x):\n    try:\n        return x + 1\n    except Exception:\n        return None', tr_full, genome)
val2 = r2["fitness_value"]
print(f"Test 2 (20/20 passed) -> fitness={val2}  {'PASS' if val2 > 0 else 'FAIL'}")

# Test 3: 10/20 tests - correctness_rate = 0.5
tr_half = {'passed_tests': 10, 'total_tests': 20, 'failed_test_ids': list(range(10)),
           'timeout_tests': [], 'crash_tests': [], 'execution_time_ms': 100, 'peak_memory_kb': 0}
r3 = scorer.calculate_fitness('def f(x): return x', tr_half, genome)
print(f"Test 3 (10/20 passed) -> fitness={r3['fitness_value']}, correctness_rate={r3['correctness_rate']}")
print(f"  breakdown: {r3['breakdown']}")

# Test 4: Property Tester
from src.property_tester import PropertyTester
import json
with open('data/train_problems.json', 'r', encoding='utf-8') as f:
    problems = json.load(f)
pt = PropertyTester()
extra = pt.generate(problems[0], n=5)
print(f"\nTest 4 (Property Tester) -> Generated {len(extra)} ephemeral tests for '{problems[0]['title']}'")
for t in extra:
    print(f"  {t['input']} => {t['expected']}")
