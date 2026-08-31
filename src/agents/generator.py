from src.client import EvoClient
from src.genome import GeneratorGenome

class GeneratorAgent:
    """
    LLM-based Generator agent. Produces code solutions based on a genome strategy.
    """
    def __init__(self, client: EvoClient):
        self.client = client

    async def solve(self, problem: dict, genome: GeneratorGenome) -> str:
        system_prompt = self._build_system_prompt(genome)
        user_prompt = self._build_user_prompt(problem, genome)
        
        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=genome.temperature
        )
        return self._extract_code(response["content"])

    def _build_system_prompt(self, genome: GeneratorGenome) -> str:
        if genome.system_instruction_variant == "expert_coder":
            return "You are an expert software engineer. Provide only the robust, clean code implementation."
        return "You are a code generation assistant. Output Python code for the given problem."

    def _build_user_prompt(self, problem: dict, genome: GeneratorGenome) -> str:
        prompt = f"Problem: {problem.get('title', 'Unknown')}\n{problem.get('description', '')}\n\n"
        
        if genome.past_code and genome.critic_feedback:
            prompt += f"Here is your previous attempt which failed:\n```python\n{genome.past_code}\n```\n\n"
            prompt += f"Here is the Critic's feedback on why it failed:\n{genome.critic_feedback}\n\n"
            prompt += "Please fix the code based on the feedback.\n\n"
            
        if genome.prompt_style == "chain_of_thought":
            prompt += "Please think step-by-step and then provide the final code inside ```python blocks."
        else:
            prompt += "Provide the code inside ```python blocks."
        return prompt

    def _extract_code(self, raw_response: str) -> str:
        # Simple markdown extraction
        if "```python" in raw_response:
            parts = raw_response.split("```python")
            if len(parts) > 1:
                return parts[1].split("```")[0].strip()
        elif "```" in raw_response:
            parts = raw_response.split("```")
            if len(parts) > 1:
                return parts[1].strip()
        return raw_response.strip()
