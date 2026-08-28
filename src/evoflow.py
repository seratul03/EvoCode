import asyncio
import json
import os
from datetime import datetime
from src.client import EvoClient
from src.event_logger import EventLogger
from src.sandbox import Sandbox
from src.fitness_scorer import FitnessScorer

from src.agents.generator import GeneratorAgent
from src.agents.code_validator import CodeValidatorAgent
from src.agents.critic import CriticAgent
from src.agents.mutator import MutatorAgent

from src.genome import GeneratorGenome, CriticGenome, MutatorGenome, EvaluatorGenome

class EvoFlowOrchestrator:
    """
    The main orchestrator for the Co-Evolutionary system.
    Manages the 4 populations, runs the generations, and records everything via EventLogger and JSON run logs.
    """
    def __init__(self, pop_size=5):
        self.client = EvoClient()
        self.logger = EventLogger()
        self.sandbox = Sandbox(timeout_seconds=5)
        self.fitness_scorer = FitnessScorer()
        
        # Agents
        self.generator = GeneratorAgent(self.client)
        self.validator = CodeValidatorAgent(self.client)
        self.critic = CriticAgent()
        self.mutator = MutatorAgent()

        self.pop_size = pop_size

        # Populations
        self.pop_generator = [GeneratorGenome() for _ in range(pop_size)]
        self.pop_critic = [CriticGenome() for _ in range(pop_size)]
        self.pop_mutator = [MutatorGenome() for _ in range(pop_size)]
        self.pop_evaluator = [EvaluatorGenome() for _ in range(pop_size)]
        
        # State tracking for the structured JSON report
        self.run_report = {
            "start_time": datetime.utcnow().isoformat(),
            "pop_size": pop_size,
            "problems_evaluated": []
        }

    async def evaluate_population(self, generation_id: int, problem: dict, problem_report: dict):
        results = []
        problem_id = problem.get("id", 0)
        
        gen_report = {
            "generation_id": generation_id + 1,
            "evaluations": [],
            "selection_and_breeding": {}
        }
        
        for i in range(self.pop_size):
            print(f"    Evaluating Genome {i+1}/{self.pop_size}...")
            gen_genome = self.pop_generator[i]
            crit_genome = self.pop_critic[i]
            mut_genome = self.pop_mutator[i]
            eval_genome = self.pop_evaluator[i]

            # 1. Execute
            code = await self.generator.solve(problem, gen_genome)
            
            # Print truncated code
            print(f"      [Code Generated] (Truncated): {code[:100].replace(chr(10), ' ')}...")
            
            # 2. Sandbox
            test_results = self.sandbox.run(code, problem.get("tests", []))
            passed = test_results["passed_tests"]
            total = test_results["total_tests"]
            print(f"      [Sandbox] Passed {passed}/{total} tests. Crashes: {len(test_results['crash_tests'])}")
            
            self.logger.log_test_result(
                problem_id, generation_id, i, 
                passed, total,
                test_results["failed_test_ids"], test_results["timeout_tests"],
                test_results["crash_tests"], test_results["execution_time_ms"], 
                test_results["peak_memory_kb"]
            )
            
            # 3. Validate
            validation = await self.validator.validate(code, problem, test_results)
            self.logger.log_validation(
                problem_id, generation_id, validation.get("is_correct", False), 
                validation.get("confidence", 0.0), str(validation.get("issues", [])), 0
            )
            
            # 4. Evaluate & 5. Aggregate
            fitness = self.fitness_scorer.calculate_fitness(code, test_results, eval_genome)
            self.logger.log_fitness("generator", i, generation_id, problem_id, fitness["fitness_value"], fitness)
            
            # 6. Critique
            diagnosis = self.critic.critique(code, test_results, validation, crit_genome)
            severity = diagnosis.get("severity", 0.0)
            primary_fail = diagnosis.get("primary_failure", "none")
            rec_mutations = diagnosis.get("recommended_mutations", [])
            print(f"      [Critic] Severity: {severity:.2f}, Primary failure: {primary_fail}, Rec. mutations: {rec_mutations}")
            print(f"      [Fitness] Score: {fitness['fitness_value']:.2f}")
            
            self.logger.log_critic(
                problem_id, generation_id, primary_fail,
                severity, diagnosis.get("code_issues", []), rec_mutations
            )
            
            results.append({
                "index": i,
                "fitness": fitness["fitness_value"],
                "diagnosis": diagnosis,
                "gen_genome": gen_genome,
                "mut_genome": mut_genome
            })
            
            gen_report["evaluations"].append({
                "genome_index": i,
                "gen_genome_snapshot": gen_genome.model_dump(),
                "generated_code": code,
                "test_results": test_results,
                "validation": validation,
                "fitness": fitness,
                "critic_diagnosis": diagnosis
            })
            
        problem_report["generations"].append(gen_report)
        return results, gen_report

    def select_and_breed(self, generation_id: int, results: list, problem_id: int, gen_report: dict):
        print("    [Selection & Breeding]")
        # Sort results by fitness descending
        results.sort(key=lambda x: x["fitness"], reverse=True)
        
        # Truncation selection: Keep top 2, breed 3
        top_k = min(2, len(results))
        top_results = results[:top_k]
        
        new_pop_generator = []
        
        survivors = [r["index"] for r in top_results]
        killed = [r["index"] for r in results[top_k:]]
        print(f"      Survivors: {survivors} | Killed: {killed}")
        
        gen_report["selection_and_breeding"]["survivors"] = survivors
        gen_report["selection_and_breeding"]["killed"] = killed
        gen_report["selection_and_breeding"]["mutations"] = []
        
        # Keep top K
        for r in top_results:
            new_pop_generator.append(r["gen_genome"])
            self.logger.log_genome("generator", r["index"], generation_id, r["gen_genome"].model_dump(), r["gen_genome"].parent_id or -1)
            
        # Breed the rest to fill pop_size
        while len(new_pop_generator) < self.pop_size:
            # Pick a parent from the top K
            parent_result = top_results[len(new_pop_generator) % top_k]
            parent_genome = parent_result["gen_genome"]
            mutator_genome = parent_result["mut_genome"]
            diagnosis = parent_result["diagnosis"]
            
            child_genome = self.mutator.propose(diagnosis, parent_genome, mutator_genome)
            child_genome.parent_id = parent_result["index"]
            child_genome.generation_id = generation_id
            
            new_pop_generator.append(child_genome)
            
            child_index = len(new_pop_generator) - 1
            print(f"      Mutated child {child_index} from parent {parent_result['index']}.")
            print(f"        Changes: {child_genome.model_dump()}")
            
            gen_report["selection_and_breeding"]["mutations"].append({
                "parent_index": parent_result["index"],
                "child_index": child_index,
                "parent_genome": parent_genome.model_dump(),
                "child_genome": child_genome.model_dump()
            })
            
            # Log mutation
            self.logger.log_mutation(
                "generator", child_index, generation_id,
                parent_genome.model_dump(), child_genome.model_dump(),
                "critic_guided", "breeding", parent_result["fitness"], 0.0
            )
            
        self.pop_generator = new_pop_generator

    def _save_structured_report(self):
        self.run_report["end_time"] = datetime.utcnow().isoformat()
        os.makedirs("structured_reports", exist_ok=True)
        
        # Windows doesn't allow colons in filenames. Using dashes.
        # Format: ddmmyyyy_hh-mm-ss
        now = datetime.now()
        filename = now.strftime("%d%m%Y_%H-%M-%S.json")
        filepath = os.path.join("structured_reports", filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.run_report, f, indent=2, ensure_ascii=False)
            
        print(f"\n[Logging] Structured report saved to: {filepath}")

    async def run_generations(self, num_generations: int, problems: list[dict]):
        print(f"--- Starting EvoFlow with {num_generations} generations on {len(problems)} problems ---")
        
        for problem in problems:
            problem_id = problem.get("id", 0)
            print(f"\n==============================")
            print(f"Evaluating Problem {problem_id}")
            print(f"==============================")
            
            problem_report = {
                "problem_id": problem_id,
                "generations": []
            }
            
            for gen in range(num_generations):
                print(f"\n  --- Generation {gen+1}/{num_generations} ---")
                
                results, gen_report = await self.evaluate_population(gen, problem, problem_report)
                
                # Check circuit breaker: If best fitness is 1.0, we found a perfect solution!
                best_fitness = max(r["fitness"] for r in results)
                print(f"  -> Best fitness in Generation {gen+1}: {best_fitness:.2f}")
                
                if best_fitness >= 1.0:
                    print(f"  [Circuit Breaker] Perfect fitness reached for Problem {problem_id}. Stopping early.")
                    gen_report["circuit_breaker_triggered"] = True
                    break
                    
                # Otherwise, select and breed
                if gen < num_generations - 1:
                    self.select_and_breed(gen, results, problem_id, gen_report)
                    
            self.run_report["problems_evaluated"].append(problem_report)
            
        # Write the final JSON report at the end of the run
        self._save_structured_report()

