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
            return (
                "You are an expert software engineer. "
                "Provide only the robust, clean, and fully correct code implementation. "
                "Pay close attention to ALL edge cases including empty inputs, negative values, "
                "and cases where no solution exists — always return the correct value rather than raising exceptions."
            )
        if genome.system_instruction_variant == "pedantic_reviewer":
            return (
                "You are a meticulous code reviewer and software engineer. "
                "Before writing any code, carefully reason about every edge case: "
                "empty inputs, negative values, no-solution cases, duplicate values, and boundary conditions. "
                "For functions that may have no valid result, ALWAYS return None rather than raising exceptions. "
                "Write only the implementation — no test code, no main block."
            )
        # standard
        return (
            "You are a code generation assistant. Output Python code for the given problem. "
            "If the problem has no valid answer for certain inputs, return None instead of raising an exception."
        )

    def _build_user_prompt(self, problem: dict, genome: GeneratorGenome) -> str:
        prompt = f"Problem: {problem.get('title', 'Unknown')}\n{problem.get('description', '')}\n\n"

        signature = problem.get("function_signature")
        if signature:
            prompt += (
                f"IMPORTANT: You MUST use the following exact function signature "
                f"and do NOT wrap your code in a class:\n```python\n{signature}\n```\n\n"
            )

        # Edge-case contract — always injected so the LLM never misses it
        prompt += (
            "CRITICAL RULES:\n"
            "1. If the problem has no valid answer for the given inputs, return None — do NOT raise an exception.\n"
            "2. Handle ALL edge cases exactly as the problem description implies "
            "(e.g. empty lists, negative numbers, zero, duplicates).\n"
            "3. Match the return type specified in the signature exactly.\n\n"
        )

        # Detect whether we are in a cache-loop and force a structural rethink
        in_cache_loop = genome.critic_feedback and "break_cache_loop" in genome.critic_feedback

        if genome.past_code and genome.critic_feedback:
            if in_cache_loop:
                prompt += (
                    "WARNING: Your previous approach has been tried multiple times and keeps failing. "
                    "You MUST use a completely different algorithm or approach — do NOT repeat the same logic.\n\n"
                    f"Previous failing attempt (DO NOT repeat this):\n```python\n{genome.past_code}\n```\n\n"
                    f"Why it failed:\n{genome.critic_feedback}\n\n"
                    "Please implement a fundamentally different solution.\n\n"
                )
            else:
                prompt += (
                    f"Here is your previous attempt which failed:\n```python\n{genome.past_code}\n```\n\n"
                    f"Here is the Critic's feedback on why it failed:\n{genome.critic_feedback}\n\n"
                    "Please fix the code based on the feedback.\n\n"
                )

        # Prompt style variants
        if genome.prompt_style == "chain_of_thought":
            steps = max(genome.reasoning_steps, 1)
            prompt += (
                f"Think step-by-step through at least {steps} reasoning steps, "
                "explicitly address every edge case, then provide your final implementation inside ```python blocks."
            )
        elif genome.prompt_style == "test_first":
            prompt += (
                "Before writing the solution, mentally run through several test cases including edge cases "
                "(empty input, negative values, no-solution cases, duplicates). "
                "Then provide your implementation inside ```python blocks."
            )
        elif genome.prompt_style == "step_by_step":
            prompt += (
                "Break the problem into clear steps:\n"
                "Step 1: Understand the input/output contract including edge cases.\n"
                "Step 2: Choose the correct algorithm.\n"
                "Step 3: Handle every edge case explicitly.\n"
                "Step 4: Write the implementation inside ```python blocks."
            )
        else:  # direct
            prompt += "Provide the implementation inside ```python blocks."

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
