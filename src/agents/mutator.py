from src.genome import GeneratorGenome, MutatorGenome
import random
import copy

_PROMPT_STYLES = ["direct", "chain_of_thought", "test_first", "step_by_step"]
_SYSTEM_VARIANTS = ["standard", "expert_coder", "pedantic_reviewer"]

class MutatorAgent:
    """
    Rule-based Mutator.
    Proposes changes to the GeneratorGenome based on the Critic's diagnosis.
    """
    def __init__(self):
        pass

    def propose(self, diagnosis: dict, current_genome: GeneratorGenome, mutator_genome: MutatorGenome) -> GeneratorGenome:
        """
        Returns a newly mutated GeneratorGenome.
        """
        new_genome = copy.deepcopy(current_genome)
        recommendations = diagnosis.get("recommended_mutations", [])

        # 1. Random mutation chance (applied BEFORE targeted mutations)
        if random.random() < mutator_genome.mutation_rate:
            new_genome.temperature = max(0.0, min(1.0, new_genome.temperature + random.uniform(-0.2, 0.2)))
            # On a random jolt, also randomly rotate prompt style for more diversity
            if random.random() < 0.5:
                new_genome.prompt_style = random.choice(_PROMPT_STYLES)
            return new_genome

        if not recommendations:
            return new_genome  # No changes needed if no issues

        # 2. Break cache loop — HIGHEST priority: force structural genome change
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
