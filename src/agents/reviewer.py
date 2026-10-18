"""
src/agents/reviewer.py

ReviewerAgent — Pre-execution static code review.

Called AFTER the GeneratorAgent produces code but BEFORE the Sandbox runs
it.  The reviewer looks for obvious bugs, missing edge-case handling, and
logic issues.  If it finds problems it returns a revised version of the
code so the Sandbox gets a cleaner attempt on the first run.

Design rules:
  - No sandbox execution, no test results — purely static LLM review.
  - Returns {"revised_code": str | None, "issues": list[str]}.
    revised_code is None when the reviewer considers the code correct as-is.
  - Gracefully degrades: on any failure, returns {"revised_code": None, "issues": []}.
  - Respects genome.verification.failure_diagnosis_strategy to control
    how deep the review goes.
  - Never overwrites code that is already syntactically broken (passes it
    through unchanged — the Sandbox crash path will handle that).
"""

import ast
from src.client import EvoClient
from src.genome import AgentGenome


class ReviewerAgent:
    """
    Pre-execution peer reviewer for generated code.

    The reviewer is intentionally positioned BEFORE any execution so its
    patches have the highest leverage — catching bugs before a wasted
    sandbox call.
    """

    SYSTEM_PROMPT = (
        "You are a meticulous code reviewer performing a pre-execution static review. "
        "You will receive a problem description and a code solution. "
        "Your job is to:\n"
        "  1. Identify bugs, missing edge-case handling, off-by-one errors, "
        "     wrong return types, or logic mistakes.\n"
        "  2. If you find issues, output a corrected version of the ENTIRE function. "
        "     Output ONLY the corrected code in a fenced code block — nothing else.\n"
        "  3. If the code looks correct, output exactly: NO_ISSUES\n\n"
        "Rules:\n"
        "  - Never change the function name or signature.\n"
        "  - Never add a main() function or test harness.\n"
        "  - Do not add unnecessary complexity — only fix clear bugs.\n"
        "  - If you are unsure, output NO_ISSUES rather than guessing.\n"
    )

    def __init__(self, client: EvoClient):
        self.client = client

    async def review(
        self,
        code: str,
        problem: dict,
        language: str,
        genome: AgentGenome,
    ) -> dict:
        """
        Statically review *code* for *problem*.

        Returns:
            {
                "revised_code": str | None,   # None means no change needed
                "issues":       list[str],     # list of issues found (may be empty)
            }
        """
        # Skip review on obviously broken code — sandbox crash path handles it
        if language == "Python" and not self._is_parseable(code):
            return {"revised_code": None, "issues": ["Syntax error — skipping review"]}

        verification = getattr(genome, "verification", None)
        depth = getattr(verification, "failure_diagnosis_strategy", "logical_trace") if verification else "logical_trace"
        user_prompt = self._build_prompt(code, problem, language, depth)

        try:
            response = await self.client.create_completion(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            raw = response.get("content", "").strip()
            return self._parse_response(raw, language)

        except Exception as e:
            print(f"      [Reviewer] Review call failed ({e}). Passing code through unchanged.")
            return {"revised_code": None, "issues": []}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_parseable(code: str) -> bool:
        """Quick Python AST parse to detect syntax errors."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _build_prompt(
        self, code: str, problem: dict, language: str, depth: str
    ) -> str:
        title = problem.get("title", "Unknown Problem")
        description = problem.get("description", "")

        # Surface a few example tests so the reviewer can validate logic
        tests = problem.get("tests", [])
        test_lines = ""
        if tests:
            sample = tests[:5]
            lines = [
                f"  Input: {t.get('input', '')}  →  Expected: {t.get('expected', '')}"
                for t in sample
            ]
            test_lines = "Test cases (for reference):\n" + "\n".join(lines)

        depth_instruction = (
            "Focus especially on edge cases: empty inputs, None/null values, "
            "duplicates, and boundary conditions."
            if depth in ("logical_trace", "comprehensive")
            else "Focus on obvious logic errors and wrong return types only."
        )

        return (
            f"Problem: {title}\n{description}\n\n"
            f"{test_lines}\n\n"
            f"Language: {language}\n\n"
            f"Code to review:\n```{language.lower()}\n{code}\n```\n\n"
            f"{depth_instruction}\n\n"
            "Output either NO_ISSUES or the complete corrected code in a fenced block."
        )

    @staticmethod
    def _parse_response(raw: str, language: str) -> dict:
        """
        Parses the reviewer's LLM response.

        If the response contains NO_ISSUES → no revision needed.
        If the response contains a code block → extract as revised_code.
        """
        if "NO_ISSUES" in raw and "```" not in raw:
            return {"revised_code": None, "issues": []}

        # Try to extract fenced code block
        lang_tag = f"```{language.lower()}"
        for tag in (lang_tag, "```python", "```java", "```cpp", "```c++", "```"):
            if tag in raw:
                parts = raw.split(tag)
                if len(parts) > 1:
                    revised = parts[1].split("```")[0].strip()
                    if revised:
                        return {
                            "revised_code": revised,
                            "issues": ["Reviewer identified issues and produced a revision."],
                        }

        # No code block found — treat as no change
        return {"revised_code": None, "issues": []}
