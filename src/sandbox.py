import subprocess
import time
import os
import json
import tempfile
import sys

class Sandbox:
    """
    Executes generated code in a restricted Docker environment with timeouts and resource limits.
    """
    def __init__(self, timeout_seconds: int = 5):
        self.timeout_seconds = timeout_seconds

    def run(self, code: str, test_cases: list[dict]) -> dict:
        """
        Runs the generated code against a list of test cases in Docker.
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

        # Create a temporary directory to mount into Docker
        with tempfile.TemporaryDirectory() as temp_dir:
            solution_path = os.path.join(temp_dir, 'solution.py')
            runner_path = os.path.join(temp_dir, 'runner.py')
            tests_path = os.path.join(temp_dir, 'tests.json')

            with open(solution_path, 'w', encoding='utf-8') as f:
                f.write(code)

            with open(tests_path, 'w', encoding='utf-8') as f:
                json.dump(test_cases, f)

            runner_code = """
import json
import sys
import traceback

with open('tests.json') as f:
    tests = json.load(f)

# Load the solution code
try:
    ns = {}
    with open('solution.py', encoding='utf-8') as f:
        exec(f.read(), ns)
except Exception as e:
    # If the file itself is invalid Python (syntax error)
    err_msg = traceback.format_exc()
    if len(err_msg) > 1000:
        err_msg = err_msg[:500] + "\\n... [TRUNCATED] ...\\n" + err_msg[-500:]
    print(json.dumps({"error": "syntax", "details": err_msg}))
    sys.exit(1)

results = []
for test in tests:
    tid = test.get('id')
    test_input = test.get('input', '')
    expected_raw = str(test.get('expected', ''))
    
    try:
        if ';' in test_input:
            parts = test_input.rsplit(';', 1)
            exec(parts[0].strip(), ns)
            result = eval(parts[1].strip(), ns)
        else:
            result = eval(test_input, ns)
            
        try:
            expected_val = eval(expected_raw)
            match = (result == expected_val) or (str(result) == str(expected_val)) or (str(result) == expected_raw)
        except Exception:
            match = (str(result).strip() == expected_raw.strip())
            if not match:
                match = (repr(result).strip("'\\\"") == expected_raw.strip("'\\\""))
                
        if match:
            results.append({"id": tid, "status": "pass"})
        else:
            results.append({"id": tid, "status": "fail", "expected": expected_raw, "actual": repr(result)})
    except Exception as e:
        err_msg = str(e)
        if len(err_msg) > 500:
            err_msg = err_msg[:250] + " ... [TRUNCATED] ... " + err_msg[-250:]
        results.append({"id": tid, "status": "crash", "error": err_msg})

print(json.dumps({"results": results}))
"""

            with open(runner_path, 'w', encoding='utf-8') as f:
                f.write(runner_code)

            start_time = time.time()
            
            # Use docker run with volume mount
            # --network none, --memory="256m", --cpus="0.5"
            cmd = [
                'docker', 'run', '--rm',
                '--network', 'none',
                '--memory', '256m',
                '--cpus', '0.5',
                '-v', f"{os.path.abspath(temp_dir)}:/workspace",
                '-w', '/workspace',
                'evocode-sandbox'
            ]
            
            try:
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=self.timeout_seconds
                )
                end_time = time.time()
                results["execution_time_ms"] = (end_time - start_time) * 1000
                
                stdout = process.stdout.decode('utf-8').strip()
                stderr = process.stderr.decode('utf-8').strip()
                
                if process.returncode != 0 and not stdout:
                    # Docker crash or OOM or Syntax Error
                    # Mark all as crash
                    for test in test_cases:
                        tid = test.get("id")
                        results["crash_tests"].append(tid)
                        results["test_outputs"].append({"id": tid, "status": "crash", "error": stderr})
                    return results

                try:
                    # Find the last line that is valid JSON (in case docker emits warnings)
                    lines = stdout.split('\n')
                    json_out = None
                    for line in reversed(lines):
                        if line.startswith('{'):
                            json_out = json.loads(line)
                            break
                            
                    if not json_out:
                        raise ValueError("No JSON output")
                        
                    if "error" in json_out and json_out["error"] == "syntax":
                        # Syntax error in the solution
                        for test in test_cases:
                            tid = test.get("id")
                            results["crash_tests"].append(tid)
                            results["test_outputs"].append({"id": tid, "status": "crash", "error": json_out["details"]})
                        return results
                        
                    for test_res in json_out.get("results", []):
                        tid = test_res["id"]
                        status = test_res["status"]
                        results["test_outputs"].append(test_res)
                        if status == "pass":
                            results["passed_tests"] += 1
                        elif status == "fail":
                            results["failed_test_ids"].append(tid)
                        elif status == "crash":
                            results["crash_tests"].append(tid)
                            
                except Exception as e:
                    # Failed to parse runner output
                    for test in test_cases:
                        tid = test.get("id")
                        results["crash_tests"].append(tid)
                        results["test_outputs"].append({"id": tid, "status": "crash", "error": "Runner output parse error"})
                    
            except subprocess.TimeoutExpired:
                end_time = time.time()
                results["execution_time_ms"] = (end_time - start_time) * 1000
                # Mark all as timeout
                for test in test_cases:
                    tid = test.get("id")
                    results["timeout_tests"].append(tid)
                    results["test_outputs"].append({"id": tid, "status": "timeout"})

        return results
