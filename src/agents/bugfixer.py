"""
Evo_fixer — The BugFixer Agent
================================
Triggered immediately after a sandbox crash within the SAME generation.
Reads the exact stack trace / compiler error and asks the LLM to patch
ONLY the broken line(s) — no algorithm rewrite, no style change.

Flow:
    Sandbox crash detected
        → EvoFixerAgent.fix(code, test_results, problem, language)
        → LLM patches the specific bug
        → Patched code is re-run in the sandbox
        → If patched result beats original, use it; else revert
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.client import EvoClient


class EvoFixerAgent:
    """
    Evo_fixer: same-generation crash patcher.

    Unlike genome mutation (which changes the *style* next generation),
    Evo_fixer reads the stack trace the sandbox already produced and
    surgically patches the code right now.
    """

    MAX_ERROR_CHARS = 2500
    MAX_CODE_CHARS = 6000

    _SYSTEM_PROMPTS = {
        "Python": (
            "You are Evo_fixer, a Python debugging specialist embedded in an evolutionary coding engine.\n"
            "Your ONLY job: fix the exact runtime error shown. Do NOT rewrite the algorithm. "
            "Do NOT change the function name or signature. Do NOT add new imports unless essential to the fix.\n"
            "Return ONLY the complete corrected Python code — no markdown fences, no explanation, no comments."
        ),
        "Java": (
            "You are Evo_fixer, a Java debugging specialist embedded in an evolutionary coding engine.\n"
            "Your ONLY job: fix the exact runtime or compilation error shown. Do NOT rewrite the algorithm. "
            "Do NOT change the class name, method name, or signature.\n"
            "Return ONLY the complete corrected Java class — no markdown fences, no explanation, no comments."
        ),
        "C++": (
            "You are Evo_fixer, a C++ debugging specialist embedded in an evolutionary coding engine.\n"
            "Your ONLY job: fix the exact runtime or compilation error shown. Do NOT rewrite the algorithm. "
            "Do NOT change the function name or signature.\n"
            "Return ONLY the complete corrected C++ solution — no markdown fences, no explanation, no comments."
        ),
    }

    def __init__(self, client: "EvoClient"):
        self.client = client

    def _extract_crash_context(self, test_results: dict, problem_tests: list) -> str:
        """
        Pairs each crash output with its triggering test input for maximum
        LLM context. Deduplicates identical error messages.
        """
        test_map = {t.get("id", idx): t for idx, t in enumerate(problem_tests)}

        seen_errors: set[str] = set()
        lines: list[str] = []

        for out in test_results.get("test_outputs", []):
            if out.get("status") != "crash":
                continue
            raw_error = (out.get("error") or "").strip()
            if not raw_error or raw_error in seen_errors:
                continue
            seen_errors.add(raw_error)

            test_id = out.get("id")
            test_case = test_map.get(test_id)
            if test_case:
                inp = test_case.get("input", "?")
                exp = test_case.get("expected", "?")
                lines.append(f"[Test {test_id}] Input: {inp} | Expected: {exp}")
            lines.append(f"Error:\n{raw_error}\n")

        combined = "\n".join(lines)
        return combined[: self.MAX_ERROR_CHARS] if combined else "Unknown runtime crash."

    def _build_user_prompt(
        self,
        code: str,
        crash_context: str,
        problem: dict,
        language: str,
    ) -> str:
        title = problem.get("title", "Unknown Problem")
        sig = problem.get("function_signature", "")
        truncated_code = code[: self.MAX_CODE_CHARS]

        return (
            f"Problem: {title}\n"
            f"Required Signature: {sig}\n\n"
            f"=== BROKEN {language.upper()} CODE ===\n"
            f"{truncated_code}\n"
            f"=== END CODE ===\n\n"
            f"=== SANDBOX CRASH REPORT ===\n"
            f"{crash_context}\n"
            f"=== END CRASH REPORT ===\n\n"
            f"Fix ONLY the bug(s) shown above. "
            f"Keep the algorithm identical. "
            f"Preserve the function/method signature exactly. "
            f"Return the complete fixed {language} code only."
        )

    def _extract_code_from_response(self, response: str, language: str) -> str:
        """
        Strips markdown fences if the LLM added them despite instructions.
        """
        fence_tags = {
            "Python": ["```python", "```py"],
            "Java": ["```java"],
            "C++": ["```cpp", "```c++", "```c"],
        }
        for tag in fence_tags.get(language, []):
            if tag in response:
                parts = response.split(tag, 1)
                if len(parts) == 2:
                    inner = parts[1].split("```", 1)[0]
                    return inner.strip()
        if "```" in response:
            parts = response.split("```")
            if len(parts) >= 3:
                return parts[1].strip()
        return response.strip()

    async def fix(
        self,
        code: str,
        test_results: dict,
        problem: dict,
        language: str,
    ) -> str | None:
        """
        Attempt to patch crash-causing code using the sandbox error output.

        Args:
            code:         The code that crashed in the sandbox.
            test_results: Full sandbox result dict (must contain 'crash_tests').
            problem:      The problem dict (for signature + test inputs).
            language:     'Python', 'Java', or 'C++'.

        Returns:
            Patched code string if the LLM produced a meaningful change.
            None if no patch was produced or the LLM returned identical code.
        """
        if not test_results.get("crash_tests"):
            return None

        system_prompt = self._SYSTEM_PROMPTS.get(language, self._SYSTEM_PROMPTS["Python"])
        crash_context = self._extract_crash_context(
            test_results, problem.get("tests", [])
        )
        user_prompt = self._build_user_prompt(code, crash_context, problem, language)

        try:
            response = await self.client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )

            raw = response.get("content", "").strip()
            if not raw:
                return None

            fixed_code = self._extract_code_from_response(raw, language)

            if fixed_code and fixed_code.strip() != code.strip():
                return fixed_code
            return None

        except Exception as exc:
            print(f"      [Evo_fixer] LLM call failed: {exc}")
            return None
