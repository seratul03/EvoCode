from src.client import EvoClient

class CodeValidatorAgent:
    """
    Independent LLM-based verification agent.
    Checks if generated code actually solves the problem or if it just passed tests by coincidence.
    """
    def __init__(self, client: EvoClient):
        self.client = client

    async def validate(self, code: str, problem: dict, test_results: dict) -> dict:
        """
        Takes the code, the problem definition, and the sandbox test results.
        Returns a dictionary with is_correct, confidence, and issues.
        """
        passed = test_results.get("passed_tests", 0)
        total = max(test_results.get("total_tests", 1), 1)
        crash_count = len(test_results.get("crash_tests", []))
        crash_rate = crash_count / total
        pass_rate = passed / total

        # Collect the distinct crash error messages to surface in the prompt
        crash_errors = list({
            out.get("error", "")
            for out in test_results.get("test_outputs", [])
            if out.get("status") == "crash" and out.get("error")
        })
        crash_error_summary = (
            "\n".join(f"  - {e}" for e in crash_errors[:5])
            if crash_errors else "  (none)"
        )

        system_prompt = (
            "You are a senior code reviewer and security auditor. "
            "Review the provided code and sandbox results to determine if the implementation truly solves the problem. "
            "Base your verdict PRIMARILY on the actual test results, not on abstract correctness. "
            "If the code crashes or raises exceptions on more than 20% of tests, set is_correct to false."
        )

        user_prompt = (
            f"Problem: {problem.get('title')}\n"
            f"{problem.get('description')}\n\n"
            f"Sandbox Results: {passed}/{total} tests passed "
            f"({crash_count} crashes, pass rate = {pass_rate:.0%}, crash rate = {crash_rate:.0%}).\n"
        )

        if crash_errors:
            user_prompt += f"Crash error messages observed:\n{crash_error_summary}\n\n"

        user_prompt += (
            f"Code:\n```python\n{code}\n```\n\n"
            "Verdict rules:\n"
            "- Set is_correct to false if crash_rate > 20%.\n"
            "- Set is_correct to false if the code raises exceptions instead of returning None for unsolvable inputs.\n"
            "- Set is_correct to true ONLY if pass_rate is high AND no systemic crash pattern is present.\n"
            "- Set confidence to reflect the pass_rate (e.g. 0.4 pass rate → confidence near 0.4).\n\n"
            "Output a JSON object with three keys: "
            "'is_correct' (boolean), 'confidence' (0.0 to 1.0), and 'issues' (list of strings)."
        )

        # Fixed behavior: low temperature for deterministic verdicts
        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1
        )

        result = self._parse_json_response(response["content"])

        # Hard override: if crash rate > 20%, never allow is_correct=True regardless of LLM verdict
        if crash_rate > 0.2 and result.get("is_correct"):
            result["is_correct"] = False
            result["confidence"] = min(result.get("confidence", 0.5), pass_rate)
            result.setdefault("issues", []).append(
                f"Overridden: crash rate {crash_rate:.0%} exceeds 20% threshold."
            )

        return result

    def _parse_json_response(self, raw: str) -> dict:
        import json
        import re

        # Try to find JSON block
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return {
                    "is_correct": bool(data.get("is_correct", False)),
                    "confidence": float(data.get("confidence", 0.5)),
                    "issues": data.get("issues", [])
                }
            except json.JSONDecodeError:
                pass

        return {
            "is_correct": False,
            "confidence": 0.0,
            "issues": ["Failed to parse validator response."]
        }
