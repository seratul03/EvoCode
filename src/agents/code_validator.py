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
        system_prompt = "You are a senior code reviewer and security auditor. " \
                        "Review the provided code to ensure it truly solves the problem, " \
                        "is safe (no infinite loops, resource exhaustion), and hasn't just overfit the tests."
        
        user_prompt = f"Problem: {problem.get('title')}\n{problem.get('description')}\n\n"
        user_prompt += f"Test Results: {test_results['passed_tests']}/{test_results['total_tests']} tests passed.\n\n"
        user_prompt += f"Code:\n```python\n{code}\n```\n\n"
        user_prompt += "Output a JSON object with three keys: 'is_correct' (boolean), 'confidence' (0.0 to 1.0), and 'issues' (list of strings)."

        # Fixed behavior: low temperature for deterministic verdicts
        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        
        return self._parse_json_response(response["content"])

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
