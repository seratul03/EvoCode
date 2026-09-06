import json as _json
import traceback as _tb
import time as _time
import tracemalloc as _tm

def fibonacci(n: int) -> int:
    if n < 0:
        return None
    elif n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n-1) + fibonacci(n-2)

tests_json = '[{"id": 1, "args": [5], "expected": 5}]'

def _run_tests():
    test_cases = _json.loads(tests_json)
    results = []
    
    # Find the first callable in the module that isn't a builtin
    fn = None
    for name, obj in list(globals().items()):
        if callable(obj) and getattr(obj, "__module__", None) == "__main__" and not name.startswith("_") and name not in ("main", "ast"):
            fn = obj
            break

    print("Found fn:", fn)

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
                results.append({"id": tid, "status": "pass", "time_ms": exec_ms, "mem_kb": mem_kb})
            else:
                results.append({"id": tid, "status": "fail", "expected": expected, "actual": actual, "time_ms": exec_ms, "mem_kb": mem_kb})
        except Exception:
            if _tm.is_tracing(): _tm.stop()
            results.append({"id": tid, "status": "crash", "error": _tb.format_exc(limit=3)})

    print(_json.dumps(results))

if __name__ == '__main__':
    _run_tests()
