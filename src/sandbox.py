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
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def run(self, code: str, test_cases: list[dict], language: str = "Python") -> dict:
        """
        Runs the generated self-contained code in Docker.
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

        with tempfile.TemporaryDirectory() as temp_dir:
            if language == "Python":
                filename = "solution.py"
                docker_cmd = ["python", filename]
            elif language == "Java":
                filename = "Solution.java"
                docker_cmd = ["sh", "-c", "javac Solution.java && java Solution"]
            elif language == "C++":
                filename = "solution.cpp"
                docker_cmd = ["sh", "-c", "g++ solution.cpp -o sol && ./sol"]
            else:
                filename = "solution.txt"
                docker_cmd = ["echo", "unsupported language"]

            solution_path = os.path.join(temp_dir, filename)

            with open(solution_path, 'w', encoding='utf-8') as f:
                f.write(code)

            start_time = time.time()
            
            cmd = [
                'docker', 'run', '--rm',
                '--network', 'none',
                '--memory', '256m',
                '--cpus', '0.5',
                '-v', f"{os.path.abspath(temp_dir)}:/workspace",
                '-w', '/workspace',
                'evocode-sandbox'
            ] + docker_cmd
            
            try:
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=self.timeout_seconds
                )
                end_time = time.time()
                results["execution_time_ms"] = (end_time - start_time) * 1000
                
                stdout = process.stdout.decode('utf-8', errors='ignore').strip()
                stderr = process.stderr.decode('utf-8', errors='ignore').strip()
                
                # The LLM was instructed to print exactly a JSON array `[{"id": 0, "status": "pass"}, ...]`
                try:
                    # Look for the JSON array in stdout
                    start_idx = stdout.find('[')
                    end_idx = stdout.rfind(']')
                    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                        json_str = stdout[start_idx:end_idx+1]
                        json_out = json.loads(json_str)
                    else:
                        raise ValueError(f"No JSON array found in stdout. Stderr: {stderr}")

                    for test_res in json_out:
                        tid = test_res.get("id")
                        status = test_res.get("status")
                        results["test_outputs"].append(test_res)
                        if status == "pass":
                            results["passed_tests"] += 1
                        elif status == "fail":
                            results["failed_test_ids"].append(tid)
                        elif status == "crash":
                            results["crash_tests"].append(tid)
                            
                except Exception as e:
                    # Failed to parse LLM's output or execution failed
                    err_msg = str(e) + f"\nStdout:\n{stdout[:200]}\nStderr:\n{stderr[:200]}"
                    for test in test_cases:
                        tid = test.get("id")
                        results["crash_tests"].append(tid)
                        results["test_outputs"].append({"id": tid, "status": "crash", "error": err_msg})
                    
            except subprocess.TimeoutExpired:
                end_time = time.time()
                results["execution_time_ms"] = (end_time - start_time) * 1000
                # Mark all as timeout
                for test in test_cases:
                    tid = test.get("id")
                    results["timeout_tests"].append(tid)
                    results["test_outputs"].append({"id": tid, "status": "timeout"})

        return results
