import json
from src.genome import GeneratorGenome, MutatorGenome
from src.client import EvoClient
import random
import copy

_PROMPT_STYLES = ["direct", "chain_of_thought", "test_first", "step_by_step"]
_SYSTEM_VARIANTS = ["standard", "expert_coder", "pedantic_reviewer"]

class MutatorAgent:
    """
    Hybrid Mutator (LLM + Rule-based).
    Proposes changes to the GeneratorGenome based on the Critic's diagnosis.
    Uses the LLM to dynamically generate structural/prompt updates if possible,
    falling back to rule-based mutations.
    """
    def __init__(self, client: EvoClient = None):
        self.client = client

    async def propose(self, diagnosis: dict, current_genome: GeneratorGenome, mutator_genome: MutatorGenome,
                winner_code: str = None, winner_language: str = None, target_language: str = None) -> GeneratorGenome:
        """
        Returns a newly mutated GeneratorGenome using the LLM (or fallback rules).
        """
        new_genome = copy.deepcopy(current_genome)
        recommendations = diagnosis.get("recommended_mutations", [])
        
        # 0. Crossover (Knowledge Sharing)
        if winner_code and winner_language and target_language:
            new_genome.crossover_instruction = (
                f"Another agent wrote a highly successful solution in {winner_language}. "
                f"Here is their code:\n\n```{winner_language.lower()}\n{winner_code}\n```\n\n"
                f"Analyze their algorithmic approach and adapt its core logic into your {target_language} solution. "
                "Do not copy syntax directly; translate the underlying strategy."
            )
        else:
            new_genome.crossover_instruction = None

        if random.random() < mutator_genome.mutation_rate:
            new_genome.temperature = max(0.0, min(1.0, new_genome.temperature + random.uniform(-0.2, 0.2)))
            if random.random() < 0.5:
                new_genome.prompt_style = random.choice(_PROMPT_STYLES)
            return new_genome

        if not recommendations:
            return new_genome

        # If LLM client is provided, try LLM-based mutation
        if self.client and "break_cache_loop" not in recommendations and "fix_crash" not in recommendations:
            try:
                llm_genome = await self._llm_mutate(diagnosis, current_genome)
                if llm_genome:
                    llm_genome.crossover_instruction = new_genome.crossover_instruction
                    return llm_genome
            except Exception as e:
                print(f"      [Mutator] LLM mutation failed: {e}. Falling back to rule-based.")

        # Fallback: Rule-based Targeted mutations
        # Break cache loop — HIGHEST priority: force structural genome change
        if "break_cache_loop" in recommendations:
            # Rotate to a different prompt style
            other_styles = [s for s in _PROMPT_STYLES if s != current_genome.prompt_style]
            new_genome.prompt_style = random.choice(other_styles)
            # Boost temperature to escape the degenerate attractor
            new_genome.temperature = min(1.0, current_genome.temperature + 0.3)
            # Switch system instruction to pedantic so the LLM gets stricter guidance
            new_genome.system_instruction_variant = "pedantic_reviewer"
            # Inject past_code and critic_feedback so the generator knows what NOT to repeat.
            # The critic_feedback string is enriched with the break_cache_loop signal so the
            # generator prompt can detect it and issue the "try a different approach" warning.
            existing_feedback = current_genome.critic_feedback or ""
            if "break_cache_loop" not in existing_feedback:
                new_genome.critic_feedback = f"break_cache_loop\n{existing_feedback}".strip()
            # Bump reasoning steps so the LLM thinks harder before writing
            new_genome.reasoning_steps = max(current_genome.reasoning_steps, 4)
            return new_genome

        # 3. Fix crash (100% crash rate fast-path from evoflow)
        if "fix_crash" in recommendations:
            new_genome.system_instruction_variant = "pedantic_reviewer"
            new_genome.reasoning_steps = max(current_genome.reasoning_steps + 2, 4)
            new_genome.temperature = min(1.0, current_genome.temperature + 0.15)
            new_genome.prompt_style = "test_first"
            return new_genome

        # 4. Targeted mutations based on remaining recommendations
        if "return_none_on_no_solution" in recommendations:
            # Specific fix: the LLM is raising instead of returning None
            new_genome.system_instruction_variant = "pedantic_reviewer"
            new_genome.prompt_style = "test_first"
            new_genome.reasoning_steps = max(current_genome.reasoning_steps + 1, 3)

        if "add_error_handling" in recommendations or "fix_edge_cases" in recommendations:
            new_genome.system_instruction_variant = "pedantic_reviewer"
            if mutator_genome.strategy_preference == "aggressive":
                new_genome.reasoning_steps = max(current_genome.reasoning_steps + 2, 4)
            else:
                new_genome.reasoning_steps = max(current_genome.reasoning_steps + 1, 3)
            # Prefer test_first or chain_of_thought for edge-case heavy failures
            if current_genome.prompt_style == "direct":
                new_genome.prompt_style = random.choice(["test_first", "chain_of_thought"])

        if "simplify_logic" in recommendations:
            new_genome.prompt_style = "step_by_step"
            new_genome.temperature = max(0.0, new_genome.temperature - 0.2)

        if "increase_reasoning_steps" in recommendations:
            new_genome.prompt_style = "chain_of_thought"
            new_genome.reasoning_steps = max(current_genome.reasoning_steps + 1, 3)

        if "change_prompt_style" in recommendations:
            other_styles = [s for s in _PROMPT_STYLES if s != current_genome.prompt_style]
            new_genome.prompt_style = random.choice(other_styles)
            # Also rotate system variant for more diversity
            other_variants = [v for v in _SYSTEM_VARIANTS if v != current_genome.system_instruction_variant]
            new_genome.system_instruction_variant = random.choice(other_variants)

        return new_genome

    async def _llm_mutate(self, diagnosis: dict, current_genome: GeneratorGenome) -> GeneratorGenome | None:
        """
        Uses Ollama to dynamically propose a mutated GeneratorGenome based on the diagnosis.
        """
        prompt = f"""
        You are an AI Evolutionary Mutator.
        Your job is to mutate the prompt engineering parameters (the 'genome') of a Generator Agent that failed to solve a problem.

        CURRENT GENOME:
        {json.dumps(current_genome.model_dump(), indent=2)}
        
        CRITIC DIAGNOSIS (Why it failed):
        {json.dumps(diagnosis, indent=2)}
        
        Your task: Return a JSON object with updated parameters for the genome.
        You may change 'temperature' (0.0 to 1.0), 'prompt_style' (direct, chain_of_thought, test_first, step_by_step), 
        'system_instruction_variant' (standard, expert_coder, pedantic_reviewer), and 'reasoning_steps' (int).
        You can also append specific advice to 'critic_feedback' to guide the agent next time.

        Respond ONLY with a valid JSON object matching the current genome structure. Do not include markdown formatting or extra text.
        """
        
        response = await self.client.create_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        try:
            content = response["content"].strip()
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            data = json.loads(content)
            
            # Merge with current
            new_genome_data = current_genome.model_dump()
            for k in ["temperature", "prompt_style", "system_instruction_variant", "reasoning_steps"]:
                if k in data:
                    new_genome_data[k] = data[k]
                    
            if "critic_feedback" in data and data["critic_feedback"]:
                new_genome_data["critic_feedback"] = data["critic_feedback"]
                
            return GeneratorGenome(**new_genome_data)
        except Exception as e:
            return None
