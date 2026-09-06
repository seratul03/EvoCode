
def fibonacci(n: int) -> int:
    if n < 0:
        return None
    elif n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

# === INJECTED TEST HARNESS ===
import json as _json
import traceback as _tb
import time as _time
import tracemalloc as _tm

def _run_tests():
    # Find the first callable in the module that isn't a builtin
    fn = None
    fns = []
    for name, obj in list(globals().items()):
        if callable(obj) and getattr(obj, "__module__", None) == "__main__" and not name.startswith("_") and name not in ("main", "ast"):
            fns.append((name, obj))
            fn = obj
            break
    print("Found fn:", fn)
    print("All matched fns:", fns)

if __name__ == '__main__':
    _run_tests()
