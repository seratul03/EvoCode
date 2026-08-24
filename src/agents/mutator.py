from src.genome import GeneratorGenome, MutatorGenome
import random
import copy

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
        
        # 1. Random mutation chance
        if random.random() < mutator_genome.mutation_rate:
            # Apply a random jolt to temperature
            new_genome.temperature = max(0.0, min(1.0, new_genome.temperature + random.uniform(-0.2, 0.2)))
            return new_genome

        # 2. Targeted mutations based on Critic diagnosis
        if not diagnosis.get("recommended_mutations"):
            return new_genome # No changes needed if no issues

        recommendations = diagnosis["recommended_mutations"]

        if "add_error_handling" in recommendations or "fix_edge_cases" in recommendations:
            new_genome.system_instruction_variant = "pedantic_reviewer"
            if mutator_genome.strategy_preference == "aggressive":
                new_genome.reasoning_steps += 2

        if "simplify_logic" in recommendations:
            new_genome.prompt_style = "step_by_step"
            new_genome.temperature = max(0.0, new_genome.temperature - 0.2)

        if "increase_reasoning_steps" in recommendations:
            new_genome.prompt_style = "chain_of_thought"
            new_genome.reasoning_steps += 1
            
        if "change_prompt_style" in recommendations:
            styles = ["direct", "chain_of_thought", "test_first", "step_by_step"]
            if current_genome.prompt_style in styles:
                styles.remove(current_genome.prompt_style)
            new_genome.prompt_style = random.choice(styles)

        return new_genome
