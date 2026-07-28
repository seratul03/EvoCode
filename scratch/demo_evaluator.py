import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.evaluator import Evaluator, Task

def run_demo():
    print("--- Mock SWE-bench Evaluator Demo ---")

    # The python -c script creates our buggy repo
    setup_script = (
        "python -c \"import os; "
        "f=open('math_lib.py','w'); f.write('def add(a, b):\\n    return a - b\\n'); f.close(); "
        "f=open('test_math.py','w'); f.write('from math_lib import add\\ndef test_add():\\n    assert add(2, 3) == 5\\ntest_add()\\n'); f.close()\""
    )

    mock_task = Task(
        instance_id="mock-math-bug-1",
        setup_script=setup_script,
        test_command="python test_math.py",
        gold_patch="<<<<<<< SEARCH\n    return a - b\n=======\n    return a + b\n>>>>>>> REPLACE",
        target_file="math_lib.py"
    )

    evaluator = Evaluator(use_docker=False)

    print(f"\n[1] Evaluating Task: {mock_task.instance_id}")
    print("Task configuration:")
    print(f"  Target File: {mock_task.target_file}")
    print(f"  Test Command: {mock_task.test_command}")

    print("\n[2] Testing with a BAD patch (should fail)...")
    bad_patch = "<<<<<<< SEARCH\n    return a - b\n=======\n    return a * b\n>>>>>>> REPLACE"
    
    result_bad = evaluator.evaluate(mock_task, bad_patch)
    print(f"Result (Success): {result_bad.get('success')}")
    print(f"Exit Code: {result_bad.get('exit_code')}")
    if not result_bad.get('success'):
        print(f"Test Logs (abbreviated):\n{result_bad.get('logs')[:200]}")

    print("\n[3] Testing with the GOLD patch (should pass)...")
    
    result_gold = evaluator.evaluate(mock_task, mock_task.gold_patch)
    print(f"Result (Success): {result_gold.get('success')}")
    print(f"Exit Code: {result_gold.get('exit_code')}")
    if result_gold.get('success'):
        print("Gold patch evaluated successfully! The tests passed.")

if __name__ == "__main__":
    run_demo()
