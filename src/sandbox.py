import subprocess
import time
import os
import json
import tempfile
import textwrap
import sys
import ast

class Sandbox:
    """
    Executes generated code in a restricted Docker environment with timeouts and resource limits.
    The sandbox injects its own test harness so the LLM only needs to write the solution function.
    """
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def _parse_tests_to_json(self, test_cases: list[dict]) -> list[dict]:
        """Converts Python-formatted inputs/expecteds into JSON-friendly native Python lists/primitives."""
        parsed = []
        for tc in test_cases:
            inp = str(tc.get("input", ""))
            exp = str(tc.get("expected", ""))
            
            try:
                node = ast.parse(inp, mode='eval')
                args = [ast.literal_eval(arg) for arg in node.body.args]
            except Exception:
                args = [inp]
                
            try:
                exp_val = ast.literal_eval(exp)
            except Exception:
                exp_val = exp
                
            parsed.append({
                "id": tc["id"],
                "args": args,
                "expected": exp_val
            })
        return parsed

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
            parsed_tests = self._parse_tests_to_json(test_cases)
            
            if language == "Python":
                full_code = self._build_python_harness(code, parsed_tests)
                filename = "solution.py"
                docker_cmd = ["python", filename]
            elif language == "Java":
                full_code = self._build_java_harness(code, parsed_tests)
                filename = "Solution.java"
                docker_cmd = ["sh", "-c", "javac -cp /opt/java-libs/json.jar Solution.java && java -cp .:/opt/java-libs/json.jar SandboxRunner"]
            elif language == "C++":
                full_code = self._build_cpp_harness(code, parsed_tests, template=template)
                filename = "solution.cpp"
                docker_cmd = ["sh", "-c", "g++ -std=c++17 -I/usr/include solution.cpp -o sol && ./sol"]
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
                
                stdout = process.stdout.decode('utf-8', errors='ignore').strip()
                stderr = process.stderr.decode('utf-8', errors='ignore').strip()

                try:
                    start_idx = stdout.find('[')
                    end_idx = stdout.rfind(']')
                    if start_idx == -1 or end_idx < start_idx:
                        raise ValueError(f"No JSON array in stdout.\nStdout: {stdout[:300]}\nStderr: {stderr[:300]}")

                    json_out = json.loads(stdout[start_idx:end_idx + 1])
                    
                    max_time = 0.0
                    max_mem = 0.0

                    for test_res in json_out:
                        tid = test_res.get("id")
                        status = test_res.get("status")
                        t_ms = float(test_res.get("time_ms", 0.0))
                        m_kb = float(test_res.get("mem_kb", 0.0))
                        
                        max_time += t_ms
                        max_mem = max(max_mem, m_kb)
                        
                        results["test_outputs"].append(test_res)
                        if status == "pass":
                            results["passed_tests"] += 1
                        elif status == "fail":
                            results["failed_test_ids"].append(tid)
                        elif status == "crash":
                            results["crash_tests"].append(tid)
                            
                    results["execution_time_ms"] = max_time
                    results["peak_memory_kb"] = max_mem

                except Exception as e:
                    err_msg = str(e)
                    for test in test_cases:
                        tid = test.get("id")
                        results["crash_tests"].append(tid)
                        results["test_outputs"].append({"id": tid, "status": "crash", "error": err_msg})
                    # Use outer time as fallback
                    end_time = time.time()
                    results["execution_time_ms"] = (end_time - start_time) * 1000

            except subprocess.TimeoutExpired:
                end_time = time.time()
                results["execution_time_ms"] = (end_time - start_time) * 1000
                for test in test_cases:
                    tid = test.get("id")
                    results["timeout_tests"].append(tid)
                    results["test_outputs"].append({"id": tid, "status": "timeout"})

        return results

    # ─── Test Harness Builders ─────────────────────────────────────────────────

    def _build_python_harness(self, solution_code: str, parsed_tests: list[dict]) -> str:
        """Appends a deterministic Python test runner to the solution code with true telemetry."""
        tests_json = json.dumps(parsed_tests)
        harness = textwrap.dedent(f"""
# === INJECTED TEST HARNESS ===
import json as _json
import traceback as _tb
import time as _time
import tracemalloc as _tm

def _run_tests():
    test_cases = _json.loads({repr(tests_json)})
    results = []
    
    # Find the first callable in the module that isn't a builtin
    fn = None
    for name, obj in list(globals().items()):
        if callable(obj) and not name.startswith("_") and name not in ("main", "ast"):
            fn = obj
            break

    for tc in test_cases:
        tid = tc["id"]
        args = tc["args"]
        expected = str(tc["expected"]).strip()
        try:
            _tm.start()
            start_time = _time.perf_counter()
            
            if fn:
                actual = str(fn(*args)).strip()
            else:
                actual = ""
                
            end_time = _time.perf_counter()
            _, peak = _tm.get_traced_memory()
            _tm.stop()
            
            exec_ms = (end_time - start_time) * 1000
            mem_kb = peak / 1024.0

            if actual == expected:
                results.append({{"id": tid, "status": "pass", "time_ms": exec_ms, "mem_kb": mem_kb}})
            else:
                results.append({{"id": tid, "status": "fail", "expected": expected, "actual": actual, "time_ms": exec_ms, "mem_kb": mem_kb}})
        except Exception as ex:
            if _tm.is_tracing(): _tm.stop()
            results.append({{"id": tid, "status": "crash", "error": _tb.format_exc(limit=2)}})
    print(_json.dumps(results))

if __name__ == '__main__':
    _run_tests()
""")
        return solution_code + "\\n" + harness

    def _build_java_harness(self, solution_code: str, parsed_tests: list[dict]) -> str:
        """Java harness using org.json for generic input deserialization and true telemetry."""
        tests_json = json.dumps(parsed_tests)
        
        runner = f"""
// === INJECTED BY SANDBOX ===
class SandboxRunner {{
    public static void main(String[] args) {{
        String jsonTests = {json.dumps(tests_json)};
        StringBuilder sb = new StringBuilder("[");
        try {{
            org.json.JSONArray cases = new org.json.JSONArray(jsonTests);
            for (int i = 0; i < cases.length(); i++) {{
                org.json.JSONObject tc = cases.getJSONObject(i);
                int id = tc.getInt("id");
                org.json.JSONArray tcArgs = tc.getJSONArray("args");
                String expected = tc.get("expected").toString().trim();
                
                String status;
                String extra = "";
                double execMs = 0;
                double memKb = 0;
                
                try {{
                    java.lang.reflect.Method solveMethod = null;
                    for (java.lang.reflect.Method m : Solution.class.getDeclaredMethods()) {{
                        if (java.lang.reflect.Modifier.isPublic(m.getModifiers()) && !m.getName().equals("main")) {{
                            solveMethod = m;
                            break;
                        }}
                    }}
                    if (solveMethod == null) throw new RuntimeException("No public method found in Solution.");
                    
                    Class<?>[] paramTypes = solveMethod.getParameterTypes();
                    Object[] parsedArgs = new Object[paramTypes.length];
                    for (int j = 0; j < paramTypes.length; j++) {{
                        parsedArgs[j] = convertJson(tcArgs.get(j), paramTypes[j]);
                    }}
                    
                    Object instance = null;
                    if (!java.lang.reflect.Modifier.isStatic(solveMethod.getModifiers())) {{
                        instance = Solution.class.getDeclaredConstructor().newInstance();
                    }}
                    
                    Runtime rt = Runtime.getRuntime();
                    rt.gc(); 
                    long startMem = rt.totalMemory() - rt.freeMemory();
                    long startTime = System.nanoTime();
                    
                    Object result = solveMethod.invoke(instance, parsedArgs);
                    
                    long endTime = System.nanoTime();
                    long endMem = rt.totalMemory() - rt.freeMemory();
                    
                    execMs = (endTime - startTime) / 1000000.0;
                    memKb = Math.max(0, endMem - startMem) / 1024.0;
                    
                    String actual = convertResult(result).trim();
                    if (actual.equals(expected)) {{
                        status = "pass";
                    }} else {{
                        status = "fail";
                        extra = ",\\"expected\\":\\"" + expected.replace("\\"", "\\\\\\"") + "\\",\\"actual\\":\\"" + actual.replace("\\"", "\\\\\\"") + "\\"";
                    }}
                }} catch (Exception e) {{
                    status = "crash";
                    String msg = e.getCause() != null ? e.getCause().toString() : e.toString();
                    extra = ",\\"error\\":\\"" + msg.replace("\\"", "'").replace("\\n", " ") + "\\"";
                }}
                
                if (i > 0) sb.append(",");
                sb.append("{{\\"id\\":").append(id)
                  .append(",\\"status\\":\\"").append(status).append("\\"")
                  .append(",\\"time_ms\\":").append(execMs)
                  .append(",\\"mem_kb\\":").append(memKb)
                  .append(extra).append("}}");
            }}
        }} catch (Exception e) {{
            sb.append("{{\\"id\\":-1,\\"status\\":\\"crash\\",\\"error\\":\\"Harness error: ").append(e.getMessage().replace("\\"", "'")).append("\\"}}");
        }}
        sb.append("]");
        System.out.println(sb.toString());
    }}
    
    private static Object convertJson(Object jsonVal, Class<?> targetType) throws Exception {{
        if (targetType == int.class || targetType == Integer.class) return ((Number)jsonVal).intValue();
        if (targetType == long.class || targetType == Long.class) return ((Number)jsonVal).longValue();
        if (targetType == double.class || targetType == Double.class) return ((Number)jsonVal).doubleValue();
        if (targetType == boolean.class || targetType == Boolean.class) return (Boolean)jsonVal;
        if (targetType == String.class) return jsonVal.toString();
        
        if (targetType.isArray() && jsonVal instanceof org.json.JSONArray) {{
            org.json.JSONArray arr = (org.json.JSONArray) jsonVal;
            Class<?> compType = targetType.getComponentType();
            Object res = java.lang.reflect.Array.newInstance(compType, arr.length());
            for (int i = 0; i < arr.length(); i++) {{
                java.lang.reflect.Array.set(res, i, convertJson(arr.get(i), compType));
            }}
            return res;
        }}
        
        if (java.util.List.class.isAssignableFrom(targetType) && jsonVal instanceof org.json.JSONArray) {{
            org.json.JSONArray arr = (org.json.JSONArray) jsonVal;
            java.util.List<Object> list = new java.util.ArrayList<>();
            for (int i = 0; i < arr.length(); i++) {{
                Object val = arr.get(i);
                if (val instanceof Number) val = ((Number)val).intValue();
                list.add(val);
            }}
            return list;
        }}
        
        return jsonVal;
    }}
    
    private static String convertResult(Object res) {{
        if (res == null) return "null";
        if (res.getClass().isArray()) {{
            StringBuilder b = new StringBuilder("[");
            int len = java.lang.reflect.Array.getLength(res);
            for (int i = 0; i < len; i++) {{
                if (i > 0) b.append(", ");
                b.append(convertResult(java.lang.reflect.Array.get(res, i)));
            }}
            b.append("]");
            return b.toString();
        }}
        return res.toString();
    }}
}}
"""
        return solution_code + "\\n" + runner

    def _build_cpp_harness(self, solution_code: str, parsed_tests: list[dict], template: str | None = None) -> str:
        """C++ harness using nlohmann::json implicit conversions and true telemetry."""
        import re
        fn_name = "solve"
        if template:
            m = re.search(r'\\b(\\w+)\\s*\\(', template)
            if m:
                candidate = m.group(1)
                if candidate not in ("if", "while", "for", "switch", "return", "class", "struct"):
                    fn_name = candidate
                    
        tests_json = json.dumps(parsed_tests).replace('\\\\', '\\\\\\\\')

        harness = f"""
// === INJECTED TEST HARNESS ===
#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <sys/resource.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

int main() {{
    const char* json_str = R"RAWJSON({tests_json})RAWJSON";
    
    try {{
        json cases = json::parse(json_str);
        std::cout << "[";
        for (size_t i = 0; i < cases.size(); i++) {{
            if (i > 0) std::cout << ",";
            int id = cases[i]["id"];
            json args = cases[i]["args"];
            std::string expected;
            if (cases[i]["expected"].is_string()) {{
                expected = cases[i]["expected"].get<std::string>();
            }} else {{
                expected = cases[i]["expected"].dump();
            }}
            
            std::string status;
            std::string extra = "";
            double execMs = 0;
            double memKb = 0;
            
            try {{
                int num_args = args.size();
                struct rusage usage_start, usage_end;
                getrusage(RUSAGE_SELF, &usage_start);
                auto t_start = std::chrono::high_resolution_clock::now();
                
                json result_json;
                if (num_args == 1) result_json = {fn_name}(args[0]);
                else if (num_args == 2) result_json = {fn_name}(args[0], args[1]);
                else if (num_args == 3) result_json = {fn_name}(args[0], args[1], args[2]);
                else if (num_args == 4) result_json = {fn_name}(args[0], args[1], args[2], args[3]);
                else throw std::runtime_error("Unsupported number of arguments");
                
                auto t_end = std::chrono::high_resolution_clock::now();
                getrusage(RUSAGE_SELF, &usage_end);
                
                std::chrono::duration<double, std::milli> diff = t_end - t_start;
                execMs = diff.count();
                memKb = usage_end.ru_maxrss - usage_start.ru_maxrss;
                if (memKb < 0) memKb = 0;
                
                std::string actual;
                if (result_json.is_string()) actual = result_json.get<std::string>();
                else actual = result_json.dump();
                
                // trim
                size_t s2 = expected.find_first_not_of(" \\t\\r\\n");
                size_t e2 = expected.find_last_not_of(" \\t\\r\\n");
                if (s2 != std::string::npos) expected = expected.substr(s2, e2 - s2 + 1);
                
                size_t s3 = actual.find_first_not_of(" \\t\\r\\n");
                size_t e3 = actual.find_last_not_of(" \\t\\r\\n");
                if (s3 != std::string::npos) actual = actual.substr(s3, e3 - s3 + 1);
                
                if (actual == expected || result_json == cases[i]["expected"]) {{
                    status = "pass";
                }} else {{
                    status = "fail";
                    
                    std::string exp_safe = expected;
                    for(size_t pos = 0; (pos = exp_safe.find("\\"", pos)) != std::string::npos; pos += 2) exp_safe.replace(pos, 1, "\\\\\\\\"");
                    
                    std::string act_safe = actual;
                    for(size_t pos = 0; (pos = act_safe.find("\\"", pos)) != std::string::npos; pos += 2) act_safe.replace(pos, 1, "\\\\\\\\"");
                    
                    extra = ",\\"expected\\":\\"" + exp_safe + "\\",\\"actual\\":\\"" + act_safe + "\\"";
                }}
            }} catch (const std::exception& ex) {{
                status = "crash";
                std::string em = ex.what();
                for(size_t pos = 0; (pos = em.find("\\"", pos)) != std::string::npos; pos += 2) em.replace(pos, 1, "'");
                extra = std::string(",\\"error\\":\\"") + em + "\\"";
            }}
            std::cout << "{{\\"id\\":" << id << ",\\"status\\":\\"" << status << "\\",\\"time_ms\\":" << execMs << ",\\"mem_kb\\":" << memKb << extra << "}}";
        }}
        std::cout << "]" << std::endl;
    }} catch (const std::exception& e) {{
        std::cout << "[{{\\"id\\":-1,\\"status\\":\\"crash\\",\\"error\\":\\"Harness setup failed\\"}}]" << std::endl;
    }}
    return 0;
}}
"""
        return solution_code + "\\n" + harness
