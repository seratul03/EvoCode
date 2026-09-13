import random
from typing import TYPE_CHECKING
from src.genome import AgentGenome

if TYPE_CHECKING:
    from src.evoflow import EvoFlowOrchestrator

class EvoBreeder:
    def __init__(self, orchestrator: 'EvoFlowOrchestrator'):
        self.orchestrator = orchestrator

    async def select_and_breed(self, results: list, generation_id: int, gen_report: dict, mode: str = "evolve"):
        if mode == "baseline_a":
            self.orchestrator.pop_generator = [AgentGenome() for _ in range(self.orchestrator.pop_size)]
            return

        viable = [r for r in results if r.get("passed_tests", 0) >= 1]
        if not viable:
            viable = results
            print("    [Viability Gate] All candidates failed. Fallback: least-bad selection.")
        else:
            eliminated = len(results) - len(viable)
            if eliminated > 0:
                print(f"    [Viability Gate] Eliminated {eliminated} zero-pass candidate(s) from selection pool.")
        results = viable

        print("    [Selection & Breeding]")
        results.sort(key=lambda x: x["fitness"], reverse=True)

        if mode == "baseline_b":
            r = results[0]
            new_genome = AgentGenome(**r["gen_genome"].model_dump())
            new_genome.past_code = gen_report["evaluations"][0]["generated_code"]
            issues = "\n- ".join(r["diagnosis"].get("code_issues", ["Unknown issues"]))
            new_genome.critic_feedback = f"Failure type: {r['diagnosis'].get('primary_failure', 'Unknown')}\nIssues:\n- {issues}"
            self.orchestrator.pop_generator = [new_genome]
            return

        if mode == "baseline_c":
            new_pop_generator = []
            for _ in range(self.orchestrator.pop_size):
                parent_result = random.choice(results)
                parent_genome = parent_result["gen_genome"]
                mutator_genome = parent_result["mut_genome"]
                blank_diagnosis = {"severity": 0.0, "primary_failure": "none", "code_issues": [], "recommended_mutations": []}
                child_genome = await self.orchestrator.mutator.propose(blank_diagnosis, parent_genome, mutator_genome)
                child_genome.parent_id = parent_result["index"]
                child_genome.generation_id = generation_id
                new_pop_generator.append(child_genome)
            self.orchestrator.pop_generator = new_pop_generator
            return

        top_k = min(2, len(results))
        top_results = results[:top_k]
        
        new_pop_generator = [None] * self.orchestrator.pop_size
        new_pop_critic = [None] * self.orchestrator.pop_size
        new_pop_mutator = [None] * self.orchestrator.pop_size
        new_pop_evaluator = [None] * self.orchestrator.pop_size
        
        survivors = [r["index"] for r in top_results]
        killed = [r["index"] for r in results[top_k:]]
        print(f"      Survivors: {survivors} | Killed: {killed}")
        
        gen_report["selection_and_breeding"]["survivors"] = survivors
        gen_report["selection_and_breeding"]["killed"] = killed
        gen_report["selection_and_breeding"]["mutations"] = []
        
        top_gen_results = top_results
        
        critic_results = sorted(results, key=lambda x: x["critic_fitness"], reverse=True)
        top_crit_results = critic_results[:top_k] if critic_results else top_results
        
        mutator_results = sorted(results, key=lambda x: x["mutator_fitness"], reverse=True)
        top_mut_results = mutator_results[:top_k] if mutator_results else top_results
        
        for i in range(len(top_results)):
            gen_r = top_gen_results[i]
            slot = gen_r["index"]
            new_pop_generator[slot] = gen_r["gen_genome"]
            self.orchestrator.logger.log_genome("generator", gen_r["index"], generation_id, gen_r["gen_genome"].model_dump(), gen_r["gen_genome"].parent_id or -1)
            
            crit_r = top_crit_results[i % len(top_crit_results)]
            new_pop_critic[slot] = crit_r["crit_genome"]
            
            mut_r = top_mut_results[i % len(top_mut_results)]
            new_pop_mutator[slot] = mut_r["mut_genome"]
            
            new_pop_evaluator[slot] = gen_r["eval_genome"]
            
        empty_slots = [s for s in range(self.orchestrator.pop_size) if new_pop_generator[s] is None]
        for n, child_index in enumerate(empty_slots):
            parent_gen_result = top_gen_results[n % len(top_gen_results)]
            parent_crit_result = top_crit_results[n % len(top_crit_results)]
            parent_mut_result = top_mut_results[n % len(top_mut_results)]
            
            parent_genome = parent_gen_result["gen_genome"]
            mutator_genome = parent_mut_result["mut_genome"]
            diagnosis = parent_gen_result["diagnosis"]
            
            target_language = self.orchestrator.generators[child_index % len(self.orchestrator.generators)].language
            
            winner_result = top_gen_results[0]
            winner_code = winner_result.get("generated_code")
            winner_language = winner_result.get("language")
            
            child_genome = await self.orchestrator.mutator.propose(
                diagnosis, 
                parent_genome, 
                mutator_genome,
                winner_code=winner_code,
                winner_language=winner_language,
                target_language=target_language
            )
            
            is_valid = await self.orchestrator.canary_pipeline.validate_mutation(child_genome, language=target_language)
            
            if not is_valid:
                print(f"      [Breeding] Canary validation failed. Rejecting mutation and keeping parent genome.")
                child_genome = parent_genome.model_copy(deep=True)
                
            child_genome.parent_id = parent_gen_result["index"]
            child_genome.parent_fitness = parent_gen_result["fitness"]
            child_genome.generation_id = generation_id
            
            new_pop_generator[child_index] = child_genome
            
            child_crit = parent_crit_result["crit_genome"].model_copy(deep=True)
            child_crit.strictness_threshold = max(0.0, min(1.0, child_crit.strictness_threshold + random.uniform(-0.1, 0.1)))
            child_crit.parent_id = parent_crit_result["index"]
            child_crit.parent_fitness = parent_crit_result["critic_fitness"]
            child_crit.generation_id = generation_id
            new_pop_critic[child_index] = child_crit
            
            child_mut = mutator_genome.model_copy(deep=True)
            child_mut.mutation_rate = max(0.0, min(1.0, child_mut.mutation_rate + random.uniform(-0.1, 0.1)))
            child_mut.parent_id = parent_mut_result["index"]
            child_mut.parent_fitness = parent_mut_result["mutator_fitness"]
            child_mut.generation_id = generation_id
            new_pop_mutator[child_index] = child_mut
            
            child_eval = parent_gen_result["eval_genome"].model_copy(deep=True)
            child_eval.sensitivity = max(0.1, child_eval.sensitivity + random.uniform(-0.1, 0.1))
            child_eval.parent_id = parent_gen_result["index"]
            child_eval.parent_fitness = parent_gen_result["fitness"]
            child_eval.generation_id = generation_id
            new_pop_evaluator[child_index] = child_eval
            
            print(f"      Mutated child {child_index} from gen-parent {parent_gen_result['index']}.")
            
            gen_report["selection_and_breeding"]["mutations"].append({
                "parent_index": parent_gen_result["index"],
                "child_index": child_index,
                "parent_genome": parent_genome.model_dump(),
                "child_genome": child_genome.model_dump()
            })
            
            self.orchestrator.logger.log_mutation(
                "generator", child_index, generation_id,
                parent_genome.model_dump(), child_genome.model_dump(),
                "critic_guided", "breeding", parent_gen_result["fitness"], 0.0
            )
            
        self.orchestrator.pop_generator = new_pop_generator
        self.orchestrator.pop_critic = new_pop_critic
        self.orchestrator.pop_mutator = new_pop_mutator
        self.orchestrator.pop_evaluator = new_pop_evaluator
