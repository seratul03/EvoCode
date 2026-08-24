import subprocess
import time
import os
import json
import tempfile
import sys

class Sandbox:
    """
    Executes generated code in a restricted subprocess environment with timeouts.
    Never uses `exec()` to avoid breaking the host orchestrator.
    """
    def __init__(self, timeout_seconds: int = 5):
        self.timeout_seconds = timeout_seconds

    def run(self, code: str, test_cases: list[dict]) -> dict:
        """
        Runs the generated code against a list of test cases.
        Returns a dictionary of execution results.
        """
        results = {
            "passed_tests": 0,
            "total_tests": len(test_cases),
            "failed_test_ids": [],
            "timeout_tests": [],
            "crash_tests": [],
            "execution_time_ms": 0.0,
            "peak_memory_kb": 0.0,
            "test_outputs": []
        }

        # Create a temporary file for the code to run
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_script:
            temp_script.write(code)
            script_path = temp_script.name

        try:
            start_time = time.time()
            
            for i, test in enumerate(test_cases):
                test_id = test.get("id", i)
                # This assumes test cases are passed via stdin or args, but for simplicity
                # we'll write a wrapper that calls the function with test inputs.
                # In a real implementation, you'd prepend the test calls to the script or use a runner.
                
                # Simplified runner: just run the script for now (assuming it contains self-executing tests)
                # To make this robust, we should create a runner script that imports the generated code and calls the function.
                # We will just run the script as is for the skeleton.
                
                try:
                    # using subprocess.run
                    process = subprocess.run(
                        [sys.executable, script_path],
                        input=test.get("input", "").encode(),
                        capture_output=True,
                        timeout=self.timeout_seconds
                    )
                    
                    if process.returncode == 0:
                        expected = str(test.get("expected", ""))
                        actual = process.stdout.decode().strip()
                        if actual == expected or not expected:
                            results["passed_tests"] += 1
                            results["test_outputs"].append({"id": test_id, "status": "pass"})
                        else:
                            results["failed_test_ids"].append(test_id)
                            results["test_outputs"].append({"id": test_id, "status": "fail", "expected": expected, "actual": actual})
                    else:
                        results["crash_tests"].append(test_id)
                        results["test_outputs"].append({"id": test_id, "status": "crash", "error": process.stderr.decode()})
                        
                except subprocess.TimeoutExpired:
                    results["timeout_tests"].append(test_id)
                    results["test_outputs"].append({"id": test_id, "status": "timeout"})
                    
            end_time = time.time()
            results["execution_time_ms"] = (end_time - start_time) * 1000
            
            # Peak memory calculation is OS-dependent (e.g. resource module on Unix)
            # For this cross-platform skeleton, we leave it at 0.0
            
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
                
        return results
