"""
Phase 0 Validator — Week 2 Gate
Runs every reference solution against its own test cases.
Uses exec() to handle multi-statement test inputs with `;`.
"""
import json
import sys

def run_validation(path):
    with open(path) as f:
        problems = json.load(f)
    
    failed = []
    for p in problems:
        ref_code = p["reference_solution"]
        pid = p["id"]
        title = p["title"]
        
        for test in p["tests"]:
            test_input = test["input"]
            expected_raw = test["expected"]
            try:
                ns = {}
                exec(ref_code, ns)
                
                # If multi-statement (contains ';'), exec all but last, eval last
                if ";" in test_input:
                    parts = test_input.rsplit(";", 1)
                    exec(parts[0].strip(), ns)
                    result = eval(parts[1].strip(), ns)
                else:
                    result = eval(test_input, ns)
                
                # Try to match: first by value (eval expected), then by str
                try:
                    expected_val = eval(expected_raw)
                    match = (result == expected_val) or (str(result) == str(expected_val)) or (str(result) == expected_raw)
                except:
                    # Fallback: compare string representations
                    match = (str(result).strip() == expected_raw.strip())
                    if not match:
                        # Also try stripping repr quotes (e.g. 'hello' vs hello)
                        match = (repr(result).strip("'\"") == expected_raw.strip("'\""))
                
                if not match:
                    failed.append({
                        "problem_id": pid,
                        "title": title,
                        "test_id": test["id"],
                        "input": test_input,
                        "expected": expected_raw,
                        "got": repr(result)
                    })
            except Exception as e:
                failed.append({
                    "problem_id": pid,
                    "title": title,
                    "test_id": test["id"],
                    "error": str(e)
                })
    return failed, len(problems)

print("=" * 60)
print("PHASE 0 -- Week 2 Gate: Reference Solution Validation")
print("=" * 60)

all_failed = []
total_probs = 0

for path in ["data/train_problems.json", "data/test_problems.json"]:
    print(f"\nValidating: {path}")
    failed, count = run_validation(path)
    total_probs += count
    all_failed.extend(failed)
    if failed:
        for item in failed:
            err = item.get("error", f"expected={item.get('expected')}, got={item.get('got')}")
            print(f"  FAIL P{item['problem_id']} ({item.get('title','')}), Test {item.get('test_id','')} -- {err}")
    else:
        print(f"  ALL {count} problems passed!")

print("\n" + "=" * 60)
if all_failed:
    print(f"GATE FAILED: {len(all_failed)} test failures across {total_probs} problems.")
    sys.exit(1)
else:
    print(f"GATE PASSED: All {total_probs} problems pass their reference solution tests.")
