import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.evaluator import Task
from evoflow.pipeline import SequentialPipeline

async def run_demo():
    print("--- Mock SWE-bench E2E Pipeline Demo ---")

    # The python -c script creates our buggy repo
    setup_script = (
        "python -c \"import os; "
        "f=open('math_lib.py','w'); f.write('def add(a, b):\\n    return a - b\\n'); f.close(); "
        "f=open('test_math.py','w'); f.write('from math_lib import add\\ndef test_add():\\n    assert add(2, 3) == 5\\ntest_add()\\n'); f.close()\""
    )

    # Note: We don't need gold_patch for the real pipeline run, 
    # but the Task definition still expects it.
    mock_task = Task(
        instance_id="mock-math-bug-1",
        setup_script=setup_script,
        test_command="python test_math.py",
        gold_patch="<<<<<<< SEARCH\n    return a - b\n=======\n    return a + b\n>>>>>>> REPLACE",
        target_file="math_lib.py"
    )

    issue_title = "math_lib.add() subtracts instead of adding"
    issue_body = "The `add(a, b)` function in `math_lib.py` seems to be subtracting `b` from `a` instead of adding. Please fix it so that the test passes."
    repo_context = "File math_lib.py:\n```python\ndef add(a, b):\n    return a - b\n```\n\nFile test_math.py:\n```python\nfrom math_lib import add\ndef test_add():\n    assert add(2, 3) == 5\ntest_add()\n```"

    pipeline = SequentialPipeline(use_docker=False)

    print(f"\n[1] Starting E2E Pipeline for Task: {mock_task.instance_id}")
    
    result = await pipeline.run(mock_task, issue_title, issue_body, repo_context)
    
    print("\n--- Pipeline Execution Complete ---")
    print(f"Final Status: {result['status']}")
    print(f"Judge Score: {result.get('score', 'N/A')}")
    print("\nFinal Patch Generated:")
    print(result.get('patch'))
    print("\nCheck logs/run_logs.jsonl for the full execution trace!")

if __name__ == "__main__":
    asyncio.run(run_demo())
