import json
from src.client import EvoClient
from src.genome import AgentGenome
from src.agents.memory_agent import MemoryHistorianAgent

# Load the persistent agent memory once at module load time.
# This is a static read — fast, no LLM call required.
_AGENT_MEMORY: str = MemoryHistorianAgent.load_memory()

class GeneratorAgent:
    """
    LLM-based Generator agent. Produces code solutions based on a genome strategy.
    When a template is provided (from TemplateAgent), the generator only fills in
    the function body — it never writes the skeleton from scratch.
    """
    def __init__(self, client: EvoClient, language: str = "Python", enable_memory: bool = True):
        self.client = client
        self.language = language
        self.enable_memory = enable_memory

    def _get_invalid_input_instruction(self) -> str:
        if self.language.lower() == "python":
            return "If no valid solution exists for an input, return None instead of raising an exception."
        elif self.language.lower() == "java":
            return "If no valid solution exists for an input, and you are returning an object (like Integer), return null. If you MUST return a primitive (like int), throw an IllegalArgumentException."
        elif self.language.lower() == "c++":
            return "If no valid solution exists for an input, and you are returning a pointer or std::optional, return nullptr or std::nullopt. If you MUST return a primitive (like int), throw std::invalid_argument. Do NOT return nullptr for primitive types."
        return "If no valid solution exists, return None/null."

    async def solve(self, problem: dict, genome: AgentGenome, template: str | None = None) -> str:
        """
        Args:
            problem:  The problem dict.
            genome:   The current AgentGenome.
            template: (Optional) A pre-filled function skeleton from TemplateAgent.
                      If provided, the generator is asked to fill in ONLY the body.
                      The generator has no knowledge of how the template was created.
        """
        system_prompt = self._build_system_prompt(genome)
        user_prompt = self._build_user_prompt(problem, genome, template)

        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=genome.temperature
        )
        return self._extract_code(response["content"])

    def _build_system_prompt(self, genome: AgentGenome) -> str:
        base_prompt = f"You are an expert software engineer specializing in {self.language}.\n"
        invalid_rule = self._get_invalid_input_instruction()

        if genome.system_instruction_variant == "expert_coder":
            core = (
                "Provide only the robust, clean, and fully correct code implementation. "
                "Pay close attention to ALL edge cases including empty inputs, negative values, "
                f"and cases where no solution exists. {invalid_rule}"
            )
        elif genome.system_instruction_variant == "pedantic_reviewer":
            core = (
                "You are a meticulous code reviewer and software engineer. "
                "Before writing any code, carefully reason about every edge case: "
                "empty inputs, negative values, no-solution cases, duplicate values, and boundary conditions. "
                f"{invalid_rule}"
            )
        else:
            # standard
            core = (
                "You are a code generation assistant. Output code for the given problem. "
                f"{invalid_rule}"
            )

        prompt = base_prompt + core

        # Inject global historical memory if available and enabled.
        # This gives the agent context about what has worked and failed in past runs.
        if _AGENT_MEMORY and self.enable_memory:
            prompt += (
                "\n\n--- GLOBAL AGENT MEMORY (Lessons from Past Runs) ---\n"
                + _AGENT_MEMORY
                + "\n--- END OF AGENT MEMORY ---\n"
                "Use the lessons above to guide your approach and avoid known failure patterns."
            )

        return prompt

    def _build_user_prompt(self, problem: dict, genome: AgentGenome, template: str | None) -> str:
        prompt = f"Problem: {problem.get('title', 'Unknown')}\n{problem.get('description', '')}\n\n"

        invalid_rule = self._get_invalid_input_instruction()
        if template:
            # ── Template Mode ──────────────────────────────────────────────────
            # The generator only sees the skeleton — it fills in the body.
            prompt += (
                "A function scaffold has been prepared for you. "
                "Your job is to implement ONLY the body of the function below.\n"
                "CRITICAL RULES:\n"
                "1. Do NOT change the function name, arguments, or return type.\n"
                "2. Do NOT add a main() function or any test code.\n"
                "3. Do NOT change the structure — if the template is a free function, keep it as a free function. "
                "If it is a class, keep it as a class. Do NOT add or remove class wrappers.\n"
                "4. Handle ALL edge cases (empty inputs, negative numbers, zero, duplicates).\n"
                f"5. {invalid_rule}\n\n"
                f"Fill in this template:\n"
                f"```{self.language.lower()}\n{template}\n```\n\n"
            )
        else:
            # ── Fallback: No Template ──────────────────────────────────────────
            prompt += (
                "CRITICAL RULES:\n"
                "1. Write ONLY the solution function/class. Do NOT write a main() function.\n"
                f"2. {invalid_rule}\n"
                "3. Handle ALL edge cases (empty inputs, negative numbers, zero, duplicates).\n"
                "4. If writing Java, your public class MUST be named exactly `Solution`.\n"
                "5. If writing C++, do NOT include a main() function, and your solution "
                "function MUST be named exactly `solve`.\n\n"
            )

        # Critic feedback from previous generation
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
        
        if genome.crossover_instruction:
            prompt += f"--- CROSSOVER KNOWLEDGE SHARING ---\n{genome.crossover_instruction}\n\n"

        prompt += f"Provide your complete {self.language} solution in ```{self.language.lower()} code blocks."
        return prompt

    def _extract_code(self, raw_response: str) -> str:
        lang_tag = f"```{self.language.lower()}"
        if lang_tag in raw_response:
            parts = raw_response.split(lang_tag)
            if len(parts) > 1:
                return parts[1].split("```")[0].strip()
        # Fallbacks
        for tag in ("```python", "```java", "```cpp", "```c++", "```"):
            if tag in raw_response:
                return raw_response.split(tag)[1].split("```")[0].strip()
        return raw_response.strip()
