import json
from src.client import EvoClient
from src.genome import GeneratorGenome

class GeneratorAgent:
    """
    LLM-based Generator agent. Produces code solutions based on a genome strategy.
    """
    def __init__(self, client: EvoClient, language: str = "Python"):
        self.client = client
        self.language = language

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
        base_prompt = f"You are an expert software engineer specializing in {self.language}.\n"
        if genome.system_instruction_variant == "expert_coder":
            return base_prompt + (
                "Provide only the robust, clean, and fully correct code implementation. "
                "Pay close attention to ALL edge cases including empty inputs, negative values, "
                "and cases where no solution exists — always return the correct value rather than raising exceptions."
            )
        if genome.system_instruction_variant == "pedantic_reviewer":
            return base_prompt + (
                "You are a meticulous code reviewer and software engineer. "
                "Before writing any code, carefully reason about every edge case: "
                "empty inputs, negative values, no-solution cases, duplicate values, and boundary conditions. "
                "For functions that may have no valid result, ALWAYS return None/null rather than raising exceptions."
            )
        # standard
        return base_prompt + (
            "You are a code generation assistant. Output code for the given problem. "
            "If the problem has no valid answer for certain inputs, return None/null instead of raising an exception."
        )

    def _build_user_prompt(self, problem: dict, genome: GeneratorGenome) -> str:
        prompt = f"Problem: {problem.get('title', 'Unknown')}\n{problem.get('description', '')}\n\n"

        # Edge-case contract
        prompt += (
            "CRITICAL RULES:\n"
            "1. If the problem has no valid answer for the given inputs, return None/null — do NOT raise an exception.\n"
            "2. Handle ALL edge cases exactly as the problem description implies "
            "(e.g. empty lists, negative numbers, zero, duplicates).\n\n"
        )

        tests_json = json.dumps(problem.get("tests", []), indent=2)
        prompt += (
            "TESTING REQUIREMENT:\n"
            f"You MUST write a complete, self-contained {self.language} program. "
            "Your program MUST include a main function that runs your solution against the following test cases.\n"
            f"TEST CASES:\n{tests_json}\n\n"
            "Your main function MUST test each case and print the results to standard output "
            "as a single JSON array in EXACTLY this format (do not print anything else!):\n"
            '[{"id": 0, "status": "pass"}, {"id": 1, "status": "fail"}, {"id": 2, "status": "crash", "error": "exception message"}]\n\n'
        )

        # Detect whether we are in a cache-loop and force a structural rethink
        in_cache_loop = genome.critic_feedback and "break_cache_loop" in genome.critic_feedback

        if genome.past_code and genome.critic_feedback:
            if in_cache_loop:
                prompt += (
                    "WARNING: Your previous approach has been tried multiple times and keeps failing. "
                    "You MUST use a completely different algorithm or approach — do NOT repeat the same logic.\n\n"
                    f"Previous failing attempt (DO NOT repeat this):\n```{self.language.lower()}\n{genome.past_code}\n```\n\n"
                    f"Why it failed:\n{genome.critic_feedback}\n\n"
                    "Please implement a fundamentally different solution.\n\n"
                )
            else:
                prompt += (
                    f"Here is your previous attempt which failed:\n```{self.language.lower()}\n{genome.past_code}\n```\n\n"
                    f"Here is the Critic's feedback on why it failed:\n{genome.critic_feedback}\n\n"
                    "Please fix the code based on the feedback.\n\n"
                )

        prompt += f"Provide your complete {self.language} code inside ```{self.language.lower()} blocks."
        return prompt

    def _extract_code(self, raw_response: str) -> str:
        # Simple markdown extraction for the specific language
        lang_tag = f"```{self.language.lower()}"
        if lang_tag in raw_response:
            parts = raw_response.split(lang_tag)
            if len(parts) > 1:
                return parts[1].split("```")[0].strip()
        # Fallbacks
        if "```python" in raw_response:
            return raw_response.split("```python")[1].split("```")[0].strip()
        elif "```java" in raw_response:
            return raw_response.split("```java")[1].split("```")[0].strip()
        elif "```cpp" in raw_response:
            return raw_response.split("```cpp")[1].split("```")[0].strip()
        elif "```" in raw_response:
            parts = raw_response.split("```")
            if len(parts) > 1:
                return parts[1].strip()
        return raw_response.strip()
