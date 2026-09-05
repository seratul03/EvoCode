import re
from src.client import EvoClient


class TemplateAgent:
    """
    A completely isolated LLM agent that reads a problem description and
    generates a language-specific function scaffold (signature + empty body).

    This call is made BEFORE and INDEPENDENTLY of the GeneratorAgent.
    The Generator only ever sees the finished template — it has no knowledge
    of how it was created, what the TemplateAgent was told, or what other
    calls happened before it.

    Output: a dict of { "Python": str, "Java": str, "C++": str }
    containing one pre-filled function skeleton per language.
    """

    SYSTEM_PROMPT_WITH_SIGNATURE = (
        "You are a function signature designer. "
        "Given a problem description and an EXACT function/class signature, output ONLY the function skeleton — "
        "no explanations, no logic, just the empty scaffolds.\n\n"
        "Rules:\n"
        "1. For Python: use the EXACT function/class name and signature provided. Use type hints. "
        "Include any necessary imports above the function.\n"
        "2. For Java: adapt the Python signature to Java. The class MUST be named `Solution`. "
        "Include no main() method.\n"
        "3. For C++: CRITICAL — write a FREE FUNCTION (no class, no struct wrapper). "
        "Include necessary headers at the top. No main() function. "
        "If the Python signature is a class, still write a free function named `solve` in C++.\n"
        "4. Output in EXACTLY this format — nothing else:\n\n"
        "```python\n<python skeleton>\n```\n\n"
        "```java\n<java skeleton>\n```\n\n"
        "```cpp\n<cpp skeleton>\n```"
    )

    SYSTEM_PROMPT = (
        "You are a function signature designer. "
        "Given a problem description, output ONLY function skeletons — "
        "no explanations, no logic, just the empty function scaffolds.\n\n"
        "Rules:\n"
        "1. The function name MUST be `solve` in all languages.\n"
        "2. Choose the most natural argument types from the problem description.\n"
        "3. Python: use type hints. Include any necessary imports above the function.\n"
        "4. Java: the class MUST be named `Solution`. Include no main() method.\n"
        "5. C++: CRITICAL — write a FREE FUNCTION (no class, no struct wrapper). "
        "Include necessary headers at the top. No main() function. "
        "Example format: `int solve(int a, int b) { return 0; }`\n"
        "6. Output in EXACTLY this format — nothing else:\n\n"
        "```python\n<python skeleton>\n```\n\n"
        "```java\n<java skeleton>\n```\n\n"
        "```cpp\n<cpp skeleton>\n```"
    )

    def __init__(self, client: EvoClient):
        self.client = client

    async def generate(self, problem: dict) -> dict:
        """
        Makes one isolated LLM call and returns templates for all three languages.
        Returns a dict: { "Python": str, "Java": str, "C++": str }
        Falls back to safe defaults if parsing fails.
        """
        description = problem.get("description", "")
        title = problem.get("title", "Unknown Problem")
        function_signature = problem.get("function_signature", "")

        if function_signature:
            # Use the exact signature from the problem data — this ensures the
            # generated code matches what the test harness expects to call.
            user_prompt = (
                f"Problem: {title}\n\n"
                f"{description}\n\n"
                f"Use this EXACT Python function/class signature:\n"
                f"```python\n{function_signature}\n```\n\n"
                "Generate skeletons in Python (using the exact signature above), Java, and C++."
            )
            system_prompt = self.SYSTEM_PROMPT_WITH_SIGNATURE
        else:
            user_prompt = (
                f"Problem: {title}\n\n"
                f"{description}\n\n"
                "Generate function skeletons in Python, Java, and C++ following the rules."
            )
            system_prompt = self.SYSTEM_PROMPT

        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,   # We want deterministic, consistent signatures
            max_tokens=512,
        )

        raw = response.get("content", "")
        return self._parse(raw)

    # ─── Parsing ──────────────────────────────────────────────────────────────

    def _parse(self, raw: str) -> dict:
        """
        Extracts the three code blocks from the LLM response.
        Falls back to minimal safe defaults if any block is missing.
        """
        python = self._extract_block(raw, "python") or self._default_python()
        java   = self._extract_block(raw, "java")   or self._default_java()
        cpp    = self._extract_block(raw, "cpp")    or self._default_cpp()

        return {
            "Python": python,
            "Java":   java,
            "C++":    cpp,
        }

    @staticmethod
    def _extract_block(text: str, lang: str) -> str:
        """Extracts the content of a ```lang ... ``` block."""
        pattern = rf"```{lang}\s*(.*?)```"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    # ─── Safe Defaults ────────────────────────────────────────────────────────
    # Used when the LLM fails to produce a parseable block.
    # These are generic stubs that the GeneratorAgent can always fill.

    @staticmethod
    def _default_python() -> str:
        return (
            "from typing import Any\n\n"
            "def solve(*args: Any) -> Any:\n"
            "    pass"
        )

    @staticmethod
    def _default_java() -> str:
        return (
            "public class Solution {\n"
            "    public Object solve(Object... args) {\n"
            "        return null;\n"
            "    }\n"
            "}"
        )

    @staticmethod
    def _default_cpp() -> str:
        return (
            "#include <string>\n\n"
            "int solve(int a, int b) {\n"
            "    return 0;\n"
            "}"
        )
