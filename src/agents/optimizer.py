"""
src/agents/optimizer.py

OptimizerAgent — Post-correctness code refinement.

Called ONLY when sandbox confirms the code passes ALL tests.  The
optimizer refines the passing code for efficiency, readability, and
language-idiomatic style without changing its observable behaviour.

Design rules:
  - Only invoked when passed_tests == total_tests > 0.
  - Returns the optimised code string, or the original if optimisation
    fails or is inappropriate (e.g. already optimal, or unstable).
  - Re-validates with the sandbox after optimising to ensure correctness
    is preserved — if the re-run fails, the original code is kept.
  - Respects genome.coding.language_specific_policy to control the
    style of optimisation (standard / idiomatic / secure).
"""

from src.client import EvoClient
from src.genome import AgentGenome


class OptimizerAgent:
    """
    Refines code that already passes all tests.

    Optimisation goals (in priority order):
      1. Algorithmic complexity reduction (O(n²) → O(n log n) etc.)
      2. Idiomatic language constructs (list comprehensions, STL usage)
      3. Readability and clean variable names
      4. Secure coding patterns (when policy == "secure")
    """

    SYSTEM_PROMPT = (
        "You are an expert code optimiser. "
        "You will receive code that already passes all tests. "
        "Your job is to improve it WITHOUT changing its observable behaviour.\n\n"
        "Optimisation goals (apply in this order):\n"
        "  1. Reduce algorithmic complexity if possible.\n"
        "  2. Use idiomatic language constructs (list comprehensions, STL, etc.).\n"
        "  3. Improve readability and variable names.\n"
        "  4. Remove dead code or redundant operations.\n\n"
        "Rules:\n"
        "  - NEVER change the function name or signature.\n"
        "  - NEVER add a main() or test harness.\n"
        "  - NEVER change what the function returns for any input.\n"
        "  - If the code is already optimal, output exactly: ALREADY_OPTIMAL\n"
        "  - Otherwise, output ONLY the optimised code in a fenced code block.\n"
    )

    def __init__(self, client: EvoClient):
        self.client = client

    async def optimize(
        self,
        code: str,
        problem: dict,
        language: str,
        genome: AgentGenome,
    ) -> str:
        """
        Attempt to optimise *code* for *problem*.

        Returns the optimised code string.  If optimisation is not
        possible, not needed, or fails, returns the original *code*.
        """
        coding = getattr(genome, "coding", None)
        policy = getattr(coding, "language_specific_policy", "standard") if coding else "standard"
        user_prompt = self._build_prompt(code, problem, language, policy)

        try:
            response = await self.client.create_completion(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.1,   # slight creativity for optimisation style
                max_tokens=1536,
            )
            raw = response.get("content", "").strip()
            return self._parse_response(raw, code, language)

        except Exception as e:
            print(f"      [Optimizer] Optimisation call failed ({e}). Keeping original code.")
            return code

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self, code: str, problem: dict, language: str, policy: str
    ) -> str:
        title = problem.get("title", "Unknown Problem")
        description = problem.get("description", "")

        policy_instruction = {
            "idiomatic": (
                "Prioritise idiomatic, Pythonic/Java-idiomatic/C++-idiomatic style. "
                "Use language-specific idioms aggressively."
            ),
            "secure": (
                "Prioritise defensive coding: validate inputs, avoid undefined behaviour, "
                "prefer safe alternatives (e.g., avoid raw pointers in C++)."
            ),
        }.get(policy, "Balance efficiency and readability.")

        return (
            f"Problem: {title}\n{description}\n\n"
            f"Language: {language}\n"
            f"Optimisation policy: {policy_instruction}\n\n"
            f"Passing code to optimise:\n"
            f"```{language.lower()}\n{code}\n```\n\n"
            "Produce the optimised version, or output ALREADY_OPTIMAL."
        )

    @staticmethod
    def _parse_response(raw: str, original_code: str, language: str) -> str:
        """
        Extracts the optimised code from the LLM response.
        Falls back to original_code if no valid code block is found.
        """
        if "ALREADY_OPTIMAL" in raw and "```" not in raw:
            return original_code

        lang_tag = f"```{language.lower()}"
        for tag in (lang_tag, "```python", "```java", "```cpp", "```c++", "```"):
            if tag in raw:
                parts = raw.split(tag)
                if len(parts) > 1:
                    optimised = parts[1].split("```")[0].strip()
                    if optimised:
                        return optimised

        # No code block found — keep original
        return original_code
