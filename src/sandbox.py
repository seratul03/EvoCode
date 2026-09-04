import subprocess
import time
import os
import json
import tempfile
import textwrap
import sys

class Sandbox:
    """
    Executes generated code in a restricted Docker environment with timeouts and resource limits.
    The sandbox injects its own test harness so the LLM only needs to write the solution function.
    """
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def run(self, code: str, test_cases: list[dict], language: str = "Python", template: str | None = None) -> dict:
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
                full_code = self._build_python_harness(code, test_cases)
                filename = "solution.py"
                docker_cmd = ["python", filename]
            elif language == "Java":
                full_code = self._build_java_harness(code, test_cases)
                filename = "Solution.java"
                docker_cmd = ["sh", "-c", "javac Solution.java && java SandboxRunner"]
            elif language == "C++":
                full_code = self._build_cpp_harness(code, test_cases, template=template)
                filename = "solution.cpp"
                docker_cmd = ["sh", "-c", "g++ -std=c++17 solution.cpp -o sol && ./sol"]
            else:
                filename = "solution.txt"
                docker_cmd = ["echo", "unsupported language"]
                full_code = code

            solution_path = os.path.join(temp_dir, filename)
            with open(solution_path, 'w', encoding='utf-8') as f:
                f.write(full_code)

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
                process = subprocess.run(cmd, capture_output=True, timeout=self.timeout_seconds)
                end_time = time.time()
                results["execution_time_ms"] = (end_time - start_time) * 1000

                stdout = process.stdout.decode('utf-8', errors='ignore').strip()
                stderr = process.stderr.decode('utf-8', errors='ignore').strip()

                try:
                    start_idx = stdout.find('[')
                    end_idx = stdout.rfind(']')
                    if start_idx == -1 or end_idx < start_idx:
                        raise ValueError(f"No JSON array in stdout.\nStdout: {stdout[:300]}\nStderr: {stderr[:300]}")

                    json_out = json.loads(stdout[start_idx:end_idx + 1])

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
                    err_msg = str(e)
                    for test in test_cases:
                        tid = test.get("id")
                        results["crash_tests"].append(tid)
                        results["test_outputs"].append({"id": tid, "status": "crash", "error": err_msg})

            except subprocess.TimeoutExpired:
                end_time = time.time()
                results["execution_time_ms"] = (end_time - start_time) * 1000
                for test in test_cases:
                    tid = test.get("id")
                    results["timeout_tests"].append(tid)
                    results["test_outputs"].append({"id": tid, "status": "timeout"})

        return results

    # ─── Test Harness Builders ─────────────────────────────────────────────────

    def _build_python_harness(self, solution_code: str, test_cases: list[dict]) -> str:
        """Appends a deterministic Python test runner to the solution code."""
        tests_json = json.dumps(test_cases)
        harness = textwrap.dedent(f"""

# === INJECTED TEST HARNESS ===
import json as _json
import traceback as _tb

def _run_tests():
    test_cases = _json.loads({repr(tests_json)})
    results = []
    for tc in test_cases:
        tid = tc["id"]
        inp = tc["input"]
        expected = str(tc["expected"]).strip()
        try:
            # Try calling with parsed args; fall back to raw string
            try:
                args = [a.strip() for a in inp.split(",")]
                # Attempt to cast to int/float where possible
                parsed = []
                for a in args:
                    try: parsed.append(int(a))
                    except ValueError:
                        try: parsed.append(float(a))
                        except ValueError: parsed.append(a)
                # Find the first callable in the module that isn't a builtin
                import inspect
                fn = None
                for name, obj in list(globals().items()):
                    if callable(obj) and not name.startswith("_") and name not in ("main",):
                        fn = obj
                        break
                actual = str(fn(*parsed)).strip()
            except Exception:
                actual = str(eval(inp)).strip()

            if actual == expected:
                results.append({{"id": tid, "status": "pass"}})
            else:
                results.append({{"id": tid, "status": "fail", "expected": expected, "actual": actual}})
        except Exception as ex:
            results.append({{"id": tid, "status": "crash", "error": _tb.format_exc(limit=2)}})
    print(_json.dumps(results))

_run_tests()
""")
        return solution_code + harness

    def _build_java_harness(self, solution_code: str, test_cases: list[dict]) -> str:
        """
        Wraps the LLM's Solution class (which must NOT have a main()) with a
        deterministic test runner that calls Solution methods via reflection.
        """
        cases_literal = self._java_cases_literal(test_cases)

        harness = f"""
// === INJECTED BY SANDBOX ===
// We add an outer class to host the main() so Solution doesn't need one.
"""
        runner = f"""
class SandboxRunner {{
    public static void main(String[] args) {{
        String[][] cases = {cases_literal};
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < cases.length; i++) {{
            int id = Integer.parseInt(cases[i][0]);
            String input = cases[i][1];
            String expected = cases[i][2].trim();
            String status;
            String extra = "";
            try {{
                String[] parts = input.split(",");
                int a = Integer.parseInt(parts[0].trim());
                int b = Integer.parseInt(parts[1].trim());

                // Find first public method on Solution (static OR instance)
                java.lang.reflect.Method solveMethod = null;
                for (java.lang.reflect.Method m : Solution.class.getDeclaredMethods()) {{
                    if (java.lang.reflect.Modifier.isPublic(m.getModifiers()) &&
                        !m.getName().equals("main")) {{
                        solveMethod = m;
                        break;
                    }}
                }}

                Object result;
                if (java.lang.reflect.Modifier.isStatic(solveMethod.getModifiers())) {{
                    result = solveMethod.invoke(null, a, b);
                }} else {{
                    // Instance method — create a default Solution object
                    result = solveMethod.invoke(Solution.class.getDeclaredConstructor().newInstance(), a, b);
                }}

                String actual = String.valueOf(result).trim();
                if (actual.equals(expected)) {{
                    status = "pass";
                }} else {{
                    status = "fail";
                    extra = ",\\"expected\\":\\"" + expected + "\\",\\"actual\\":\\"" + actual + "\\"";
                }}
            }} catch (Exception e) {{
                status = "crash";
                String msg = e.getCause() != null ? e.getCause().getMessage() : e.getMessage();
                extra = ",\\"error\\":\\"" + (msg == null ? "null" : msg.replace("\\"", "'")) + "\\"";
            }}
            if (i > 0) sb.append(",");
            sb.append("{{\\"id\\":").append(id)
              .append(",\\"status\\":\\"").append(status).append("\\"")
              .append(extra).append("}}");
        }}
        sb.append("]");
        System.out.println(sb.toString());
    }}
}}
"""
        return solution_code + runner

    def _build_cpp_harness(self, solution_code: str, test_cases: list[dict], template: str | None = None) -> str:
        """Appends a deterministic C++ main() to the solution code.
        
        If a template is provided, extracts the real function name from it.
        Falls back to 'solve' if no template or name cannot be parsed.
        """
        import re
        fn_name = "solve"  # safe default
        if template:
            # Match: return_type fn_name(args)  — e.g. 'int solve(int a, int b)'
            m = re.search(r'\b(\w+)\s*\(', template)
            if m:
                candidate = m.group(1)
                # Skip keywords that aren't function names
                if candidate not in ("if", "while", "for", "switch", "return", "class", "struct"):
                    fn_name = candidate
        cases_lines = []
        for tc in test_cases:
            inp = str(tc["input"]).replace('"', '\\"')
            exp = str(tc["expected"]).replace('"', '\\"')
            # In f-string: {{ → {, so we need 4 braces to get { id, "inp", "exp" }
            cases_lines.append(f'    {{ {tc["id"]}, "{inp}", "{exp}" }}')
        cases_init = ",\n".join(cases_lines)

        harness = f"""

// === INJECTED TEST HARNESS ===
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>

struct _Case {{ int id; std::string input; std::string expected; }};

int main() {{
    std::vector<_Case> cases = {{
{cases_init}
    }};

    std::cout << "[";
    for (size_t i = 0; i < cases.size(); i++) {{
        if (i > 0) std::cout << ",";
        int id = cases[i].id;
        std::string inp  = cases[i].input;
        std::string expected = cases[i].expected;
        std::string status;
        std::string extra = "";
        try {{
            // Parse comma-separated ints from input string
            std::istringstream ss(inp);
            std::string tok;
            std::vector<int> nums;
            while (std::getline(ss, tok, ',')) {{
                // trim
                size_t s = tok.find_first_not_of(" \\t");
                size_t e = tok.find_last_not_of(" \\t");
                if (s != std::string::npos) tok = tok.substr(s, e - s + 1);
                nums.push_back(std::stoi(tok));
            }}
            auto result = {fn_name}(nums[0], nums[1]);
            std::string actual = std::to_string(result);
            // trim expected
            size_t s2 = expected.find_first_not_of(" \\t");
            size_t e2 = expected.find_last_not_of(" \\t");
            if (s2 != std::string::npos) expected = expected.substr(s2, e2 - s2 + 1);
            if (actual == expected) {{
                status = "pass";
            }} else {{
                status = "fail";
                extra = ",\\"expected\\":\\"" + expected + "\\",\\"actual\\":\\"" + actual + "\\"";
            }}
        }} catch (const std::exception& ex) {{
            status = "crash";
            extra = std::string(",\\"error\\":\\"") + ex.what() + "\\"";
        }}
        std::cout << "{{\\"id\\":" << id << ",\\"status\\":\\"" << status << "\\"" << extra << "}}";
    }}
    std::cout << "]" << std::endl;
    return 0;
}}
"""
        return solution_code + harness

    def _java_cases_literal(self, test_cases: list[dict]) -> str:
        rows = []
        for tc in test_cases:
            inp = str(tc["input"]).replace('"', '\\"')
            exp = str(tc["expected"]).replace('"', '\\"')
            rows.append(f'{{"{tc["id"]}", "{inp}", "{exp}"}}')
        return "{\n    " + ",\n    ".join(rows) + "\n}"
