"""
TestAugmentor — Layer 1 of EvoCode's 4-Layer Correctness System.

Expands each problem's fixed test suite from ~10 to 20 tests by:
1. Parsing the function signature to understand argument types.
2. Generating type-aware random inputs (normal, edge, adversarial, stress).
3. Executing the problem's reference_solution locally to derive expected outputs.
4. Deduplicating against existing tests before appending.

The augmented tests are written back to the problem JSON files once via
`scripts/augment_tests.py`. They are deterministic (seeded per problem ID)
so re-running the script produces identical results.
"""

import re
import random
import string
from typing import Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Sentinel object returned by _safe_call when the reference solution times out.
_TIMEOUT_SENTINEL = object()


class TestAugmentor:
    """
    Augments the fixed test suite of a problem using its reference_solution.
    Produces a target of `target_count` total tests (default 20).
    """

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def augment_problem(self, problem: dict, target_count: int = 20) -> dict:
        """
        Returns a *new* problem dict with an expanded 'tests' list.
        The original dict is never mutated.
        """
        existing_tests: list[dict] = problem.get("tests", [])
        if len(existing_tests) >= target_count:
            return problem

        func_sig: str = problem.get("function_signature", "")
        ref_solution: str = problem.get("reference_solution", "")

        # Skip class-based problems (e.g. MinStack) -- we can't auto-generate
        # method-call sequences from a single function signature.
        if func_sig.strip().startswith("class"):
            return problem

        func_name: str = self._extract_func_name(func_sig)
        params: list[dict] = self._parse_params(func_sig)

        if not func_name or not ref_solution or not params:
            return problem

        # Execute the reference solution in a safe namespace
        ns: dict = {}
        try:
            exec(ref_solution, ns)  # noqa: S102
        except Exception:
            return problem

        ref_func = ns.get(func_name)
        if not callable(ref_func):
            return problem

        # Seed RNG per problem ID for deterministic augmentation
        rng = random.Random(problem.get("id", 0) * 31337)

        existing_inputs: set[str] = {t["input"] for t in existing_tests}
        next_id: int = (max(t["id"] for t in existing_tests) + 1) if existing_tests else 0

        new_tests: list[dict] = []
        needed: int = target_count - len(existing_tests)
        attempts: int = 0
        max_attempts: int = needed * 20

        # Generate in four passes to ensure diversity
        generators = [
            lambda: self._generate_normal(params, rng),
            lambda: self._generate_edge(params, rng),
            lambda: self._generate_adversarial(params, rng),
            lambda: self._generate_stress(params, rng),
        ]

        pass_idx = 0
        while len(new_tests) < needed and attempts < max_attempts:
            attempts += 1
            gen = generators[pass_idx % len(generators)]
            pass_idx += 1
            try:
                args = gen()
                input_str = f"{func_name}({', '.join(repr(a) for a in args)})"
                if input_str in existing_inputs:
                    continue

                expected = self._safe_call(ref_func, args, timeout=1.0)
                if expected is _TIMEOUT_SENTINEL:
                    continue  # skip inputs that cause reference to hang

                new_tests.append({
                    "id": next_id,
                    "input": input_str,
                    "expected": repr(expected),
                })
                existing_inputs.add(input_str)
                next_id += 1
            except Exception:
                continue

        augmented = dict(problem)
        augmented["tests"] = existing_tests + new_tests
        return augmented

    # -------------------------------------------------------------------------
    # Signature Parsing
    # -------------------------------------------------------------------------

    def _safe_call(self, func, args: list, timeout: float = 1.0):
        """
        Execute func(*args) with a wall-clock timeout.
        Returns _TIMEOUT_SENTINEL if the call exceeds `timeout` seconds.
        """
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(func, *args)
            try:
                return future.result(timeout=timeout)
            except (FuturesTimeoutError, Exception):
                return _TIMEOUT_SENTINEL

    def _extract_func_name(self, sig: str) -> str:
        m = re.match(r"def\s+(\w+)\s*\(", sig)
        return m.group(1) if m else ""

    def _parse_params(self, sig: str) -> list[dict]:
        """Extract parameter names and type hints from a function signature."""
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

    # -------------------------------------------------------------------------
    # Value Generators
    # -------------------------------------------------------------------------

    def _generate_value(self, type_hint: str, rng: random.Random,
                        mode: str = "normal") -> Any:
        """Dispatch to the correct generator based on type hint and mode."""
        th = type_hint.lower()

        # Integers
        if th in ("int", "integer") or th.startswith("optional[int"):
            ranges = {
                "normal":      (-50, 50),
                "edge":        (0, 0),    # handled below with specific edge values
                "adversarial": (-20, 20),
                "stress":      (0, 20),   # safe cap: handles recursion/DP without blowup
            }
            lo, hi = ranges.get(mode, (-50, 50))
            if mode == "edge":
                return rng.choice([0, 1, -1, 2, -2])
            return rng.randint(lo, hi)

        # Floats
        if "float" in th:
            if mode == "edge":
                return rng.choice([0.0, 1.0, -1.0])
            return round(rng.uniform(-100.0, 100.0), 2)

        # Booleans
        if "bool" in th:
            return rng.choice([True, False])

        # Strings
        if th in ("str", "string") or (th.startswith("str") and "[" not in th):
            if mode == "edge":
                return rng.choice(["", "a", " ", "aaaa"])
            length = rng.randint(1, 12) if mode != "stress" else rng.randint(20, 50)
            charset = string.ascii_lowercase + "0123456789"
            return "".join(rng.choices(charset, k=length))

        # List[int]
        if "list[int]" in th or th == "list[int]":
            size = {"normal": (2, 10), "edge": (0, 2),
                    "adversarial": (2, 8), "stress": (15, 30)}.get(mode, (2, 10))
            n = rng.randint(*size)
            if mode == "edge" and n == 0:
                return []
            lo, hi = (-10, 10) if mode == "normal" else (-1000, 1000)
            vals = [rng.randint(lo, hi) for _ in range(n)]
            if mode == "adversarial":
                # Duplicate-heavy to stress hash-map / set solutions
                seed_val = rng.randint(-5, 5)
                vals = [seed_val] * (n // 2) + [rng.randint(-10, 10) for _ in range(n - n // 2)]
                rng.shuffle(vals)
            return vals

        # List[str]
        if "list[str]" in th:
            size = rng.randint(1, 6) if mode != "stress" else rng.randint(20, 50)
            length = 4 if mode != "stress" else 10
            return ["".join(rng.choices(string.ascii_lowercase, k=rng.randint(1, length)))
                    for _ in range(size)]

        # List[List[int]] / matrix
        if "list[list" in th:
            rows = rng.randint(1, 4)
            cols = rng.randint(1, 4)
            return [[rng.randint(0, 9) for _ in range(cols)] for _ in range(rows)]

        # Generic list fallback
        if "list" in th:
            size = rng.randint(1, 8)
            return [rng.randint(-20, 20) for _ in range(size)]

        # Dict
        if "dict" in th:
            size = rng.randint(1, 5)
            return {"".join(rng.choices(string.ascii_lowercase, k=3)): rng.randint(0, 10)
                    for _ in range(size)}

        # Tuple
        if "tuple" in th:
            return tuple(rng.randint(-10, 10) for _ in range(2))

        # Fallback: return a small int
        return rng.randint(0, 10)

    def _generate_args(self, params: list[dict], rng: random.Random,
                       mode: str = "normal") -> list:
        return [self._generate_value(p["type"], rng, mode) for p in params]

    def _generate_normal(self, params, rng):
        return self._generate_args(params, rng, "normal")

    def _generate_edge(self, params, rng):
        return self._generate_args(params, rng, "edge")

    def _generate_adversarial(self, params, rng):
        return self._generate_args(params, rng, "adversarial")

    def _generate_stress(self, params, rng):
        return self._generate_args(params, rng, "stress")
