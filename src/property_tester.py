"""
src/property_tester.py -- Layer 2 of EvoCode's 4-Layer Correctness System.

Generates EPHEMERAL random test cases at runtime before each sandbox evaluation.
Unlike Layer 1 (fixed augmented tests), these tests are freshly generated each
time evaluate_population is called, making it impossible for generated code to
game the test suite across generations.

Each call to generate() uses the current system time as a seed component,
ensuring unique test cases every invocation.

These tests are appended to the fixed test suite in memory only — they are
never persisted to disk.
"""

import re
import random
import string
import time
from typing import Any


class PropertyTester:
    """
    Generates N ephemeral random test cases for a problem at runtime.
    Uses the problem's reference_solution to derive correct expected outputs.

    Usage:
        extra_tests = PropertyTester().generate(problem, n=5)
        all_tests = problem["tests"] + extra_tests
    """

    def generate(self, problem: dict, n: int = 5) -> list[dict]:
        """
        Generate n random test cases. Returns an empty list if the
        reference_solution cannot be executed or the function signature
        cannot be parsed.
        """
        func_sig: str = problem.get("function_signature", "")
        ref_solution: str = problem.get("reference_solution", "")
        func_name: str = self._extract_func_name(func_sig)
        params: list[dict] = self._parse_params(func_sig)

        if not func_name or not ref_solution or not params:
            return []

        # Execute reference solution safely
        ns: dict = {}
        try:
            exec(ref_solution, ns)  # noqa: S102
        except Exception:
            return []

        ref_func = ns.get(func_name)
        if not callable(ref_func):
            return []

        # Use time + problem ID as seed so each generation call is unique
        rng = random.Random(int(time.time() * 1000) ^ (problem.get("id", 0) * 997))

        # Figure out a safe starting ID that won't clash with existing tests
        existing_tests = problem.get("tests", [])
        next_id = (max(t["id"] for t in existing_tests) + 1) if existing_tests else 1000

        results: list[dict] = []
        existing_inputs: set[str] = {t["input"] for t in existing_tests}
        attempts = 0
        max_attempts = n * 15

        while len(results) < n and attempts < max_attempts:
            attempts += 1
            try:
                args = [self._generate_value(p["type"], rng) for p in params]
                input_str = f"{func_name}({', '.join(repr(a) for a in args)})"

                if input_str in existing_inputs:
                    continue

                expected = ref_func(*args)
                results.append({
                    "id": next_id,
                    "input": input_str,
                    "expected": repr(expected),
                    "_ephemeral": True,   # Tag so logs can distinguish layer sources
                })
                existing_inputs.add(input_str)
                next_id += 1
            except Exception:
                continue

        return results

    # -------------------------------------------------------------------------
    # Signature Parsing (mirrors TestAugmentor — intentionally standalone)
    # -------------------------------------------------------------------------

    def _extract_func_name(self, sig: str) -> str:
        m = re.match(r"def\s+(\w+)\s*\(", sig)
        return m.group(1) if m else ""

    def _parse_params(self, sig: str) -> list[dict]:
        m = re.match(r"def\s+\w+\s*\((.*?)\)\s*(?:->.*)?:", sig, re.DOTALL)
        if not m:
            return []
        params_str = m.group(1).strip()
        params: list[dict] = []
        for raw in params_str.split(","):
            raw = raw.strip()
            if not raw or raw == "self":
                continue
            if ":" in raw:
                name, hint = raw.split(":", 1)
                hint = hint.split("=")[0].strip()
            else:
                name = raw.split("=")[0].strip()
                hint = "any"
            params.append({"name": name.strip(), "type": hint.lower()})
        return params

    def _generate_value(self, type_hint: str, rng: random.Random) -> Any:
        th = type_hint.lower()

        if th in ("int", "integer") or th.startswith("optional[int"):
            # Mix of small, large, and boundary values
            return rng.choice([
                rng.randint(-100, 100),
                rng.choice([0, 1, -1, 2, -2, 10 ** 6, -(10 ** 6)]),
            ])

        if "float" in th:
            return round(rng.uniform(-1000.0, 1000.0), 3)

        if "bool" in th:
            return rng.choice([True, False])

        if th in ("str", "string") or (th.startswith("str") and "[" not in th):
            length = rng.randint(0, 20)
            charset = string.ascii_lowercase + string.digits + "!@#_- "
            return "".join(rng.choices(charset, k=length))

        if "list[int]" in th or th == "list[int]":
            size = rng.randint(0, 20)
            lo, hi = rng.choice([(-10, 10), (-10**6, 10**6), (0, 100)])
            vals = [rng.randint(lo, hi) for _ in range(size)]
            # Randomly include all-same, sorted, or reversed variants
            variant = rng.randint(0, 3)
            if variant == 1 and vals:
                vals = sorted(vals)
            elif variant == 2 and vals:
                vals = sorted(vals, reverse=True)
            elif variant == 3 and vals:
                seed_val = rng.randint(-5, 5)
                vals = [seed_val] * size
            return vals

        if "list[str]" in th:
            size = rng.randint(0, 10)
            return ["".join(rng.choices(string.ascii_lowercase, k=rng.randint(1, 8)))
                    for _ in range(size)]

        if "list[list" in th:
            rows = rng.randint(1, 5)
            cols = rng.randint(1, 5)
            return [[rng.randint(0, 9) for _ in range(cols)] for _ in range(rows)]

        if "list" in th:
            size = rng.randint(0, 10)
            return [rng.randint(-20, 20) for _ in range(size)]

        if "dict" in th:
            size = rng.randint(0, 5)
            return {
                "".join(rng.choices(string.ascii_lowercase, k=3)): rng.randint(0, 10)
                for _ in range(size)
            }

        if "tuple" in th:
            return tuple(rng.randint(-10, 10) for _ in range(2))

        # Fallback
        return rng.randint(0, 50)
