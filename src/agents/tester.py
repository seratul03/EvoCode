from src.client import EvoClient

class TesterAgent:
    """
    Evaluates if the generated code is a genuine algorithmic attempt or a hardcoded cheat.
    """
    def __init__(self, client: EvoClient, language: str = "Python"):
        self.client = client
        self.language = language
        self.system_prompt = (
            f"You are Evo_Tester, a strict code reviewer. You review {self.language} code.\n"
            "Your job is to determine if the provided code is a genuine algorithmic solution "
            "to the problem, or if it 'cheats' by hardcoding specific output values for specific inputs "
            "(e.g., using a switch statement to return exact test case answers instead of computing them).\n\n"
            "Respond strictly with a single word: 'VALID' if it is a genuine algorithm, or 'INVALID' if it hardcodes/cheats."
        )

    async def evaluate(self, problem: dict, code: str) -> bool:
        """
        Returns True if the code is valid, False if it is invalid (cheating).
        """
        prompt = (
            f"Problem Description: {problem.get('description', '')}\n\n"
            f"Code to evaluate:\n{code}\n\n"
            "Does this code genuinely attempt to solve the algorithmic problem, or does it cheat by hardcoding answers?\n"
            "Reply strictly with VALID or INVALID."
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.client.create_completion(messages=messages, max_tokens=10)
        
        content = response.get("content", "")
        if "INVALID" in content.upper():
            return False
        return True
