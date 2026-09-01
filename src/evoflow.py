import asyncio
import json
import os
import random
from datetime import datetime
from src.client import EvoClient
from src.event_logger import EventLogger
from src.sandbox import Sandbox
from src.fitness_scorer import FitnessScorer
from src.property_tester import PropertyTester   # Layer 2

from src.agents.generator import GeneratorAgent
from src.agents.code_validator import CodeValidatorAgent
from src.agents.critic import CriticAgent
from src.agents.mutator import MutatorAgent

import ast
from src.genome import GeneratorGenome, CriticGenome, MutatorGenome, EvaluatorGenome

def _normalize_code(code: str) -> str:
    try:
        parsed = ast.parse(code)
        for node in ast.walk(parsed):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Constant, ast.Str)):
                    node.body.pop(0)
        return ast.unparse(parsed).strip()
    except Exception:
        return "".join(code.split())

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
        self.property_tester = PropertyTester()   # Layer 2

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
        
        self.code_cache = {}

        # Layer 4: validator used only for evolve mode (set in run_generations)
        self.use_validator = True

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

            # 1. Generate
            code = await self.generator.solve(problem, gen_genome)
            safe_code = code[:100].replace(chr(10), ' ').encode('ascii', 'replace').decode('ascii')
            print(f"      [Code Generated] (Truncated): {safe_code}...")
            
            code_hash = hash(_normalize_code(code))
            if code_hash in self.code_cache:
                print(f"      [CACHE HIT] Generated code is identical to a previous run. Reusing results.")
                cached = self.code_cache[code_hash]
                test_results, validation, fitness, diagnosis = cached["test_results"], cached["validation"], cached["fitness"], cached["diagnosis"]
                passed, total = test_results["passed_tests"], test_results["total_tests"]
                
                # Inject a warning so mutator forces a change if it gets this diagnosis
                if "break_cache_loop" not in diagnosis.get("recommended_mutations", []):
                    diagnosis.setdefault("recommended_mutations", []).append("break_cache_loop")
                if not any("WARNING: You generated this exact code" in str(iss) for iss in diagnosis.get("code_issues", [])):
                    diagnosis.setdefault("code_issues", []).append("WARNING: You generated this exact code previously and it failed. Try a fundamentally different approach.")
            else:
                # 2. Layer 2 — Property-Based Tests: append ephemeral random cases
                extra_tests = self.property_tester.generate(problem, n=5)
                all_tests = problem.get("tests", []) + extra_tests

                # 3. Sandbox with full test suite (fixed + ephemeral)
                test_results = self.sandbox.run(code, all_tests)
                passed = test_results["passed_tests"]
                total = test_results["total_tests"]
                print(f"      [Sandbox] Passed {passed}/{total} tests "
                      f"(+{len(extra_tests)} ephemeral). "
                      f"Crashes: {len(test_results['crash_tests'])}")

                self.logger.log_test_result(
                    problem_id, generation_id, i,
                    passed, total,
                    test_results["failed_test_ids"], test_results["timeout_tests"],
                    test_results["crash_tests"], test_results["execution_time_ms"],
                    test_results["peak_memory_kb"]
                )

                # 4. Layer 4 — Validate (LLM validator only active in evolve mode)
                if self.use_validator:
                    validation = await self.validator.validate(code, problem, test_results)
                else:
                    # Baselines: derive correctness signal directly from sandbox
                    validation = {
                        "is_correct": passed == total and total > 0,
                        "confidence": passed / max(total, 1),
                        "issues": [] if passed == total else [f"Failed {total - passed}/{total} tests."]
                    }
                self.logger.log_validation(
                    problem_id, generation_id, validation.get("is_correct", False),
                    validation.get("confidence", 0.0), str(validation.get("issues", [])), 0
                )

                # 5. Layer 3B — Multiplicative Fitness (correctness_rate × quality)
                fitness = self.fitness_scorer.calculate_fitness(code, test_results, eval_genome)
                self.logger.log_fitness("generator", i, generation_id, problem_id, fitness["fitness_value"], fitness)

                # 6. Critique (or bypass if 100% crash rate)
                if len(test_results["crash_tests"]) == total and total > 0:
                    print("      [Fast-Track] 100% Crash Rate. Bypassing Critic API.")
                    error_msgs = [out.get("error", "Unknown Crash") for out in test_results.get("test_outputs", []) if out.get("error")]
                    first_error = error_msgs[0] if error_msgs else "Unknown Crash"
                    diagnosis = {
                        "severity": 1.0,
                        "primary_failure": "runtime_crash",
                        "code_issues": [first_error],
                        "recommended_mutations": ["fix_crash"]
                    }
                else:
                    diagnosis = self.critic.critique(code, test_results, validation, crit_genome)
                
                self.code_cache[code_hash] = {
                    "test_results": test_results,
                    "validation": validation,
                    "fitness": fitness,
                    "diagnosis": diagnosis
                }

            severity = diagnosis.get("severity", 0.0)
            primary_fail = diagnosis.get("primary_failure", "none")
            rec_mutations = diagnosis.get("recommended_mutations", [])
            print(f"      [Critic] Severity: {severity:.2f}, Failure: {primary_fail}, "
                  f"Mutations: {rec_mutations}")
            print(f"      [Fitness] Score: {fitness['fitness_value']:.4f} "
                  f"(correctness={fitness.get('correctness_rate', passed/max(total,1)):.2f} x quality={fitness.get('quality_score', 0):.2f})")

            self.logger.log_critic(
                problem_id, generation_id, primary_fail,
                severity, diagnosis.get("code_issues", []), rec_mutations
            )

            results.append({
                "index": i,
                "fitness": fitness["fitness_value"],
                "passed_tests": passed,        # Layer 3A: needed for viability gate
                "total_tests": total,
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

    def select_and_breed(self, generation_id: int, results: list, problem_id: int, gen_report: dict, mode: str = "evolve"):
        if mode == "baseline_a":
            # Zero-shot: No feedback, no mutation. Keep same blank slate genomes.
            self.pop_generator = [GeneratorGenome() for _ in range(self.pop_size)]
            return

        # --- Layer 3A: Viability Gate ---
        # Candidates that pass 0 tests cannot be parents — they contribute
        # no correctness signal and would corrupt the gene pool.
        viable = [r for r in results if r.get("passed_tests", 0) >= 1]
        if not viable:
            # Fallback: if every candidate failed, keep the highest-fitness ones
            # (they may have partially timed out vs fully crashed — least-bad wins)
            viable = results
            print("    [Viability Gate] All candidates failed. Fallback: least-bad selection.")
        else:
            eliminated = len(results) - len(viable)
            if eliminated > 0:
                print(f"    [Viability Gate] Eliminated {eliminated} zero-pass candidate(s) from selection pool.")
        results = viable

        print("    [Selection & Breeding]")
        # Sort viable results by fitness descending
        results.sort(key=lambda x: x["fitness"], reverse=True)

        if mode == "baseline_b":
            # Static Reflection: Pop size is 1. Feed back diagnosis and code into the same genome.
            r = results[0]
            new_genome = GeneratorGenome(**r["gen_genome"].model_dump())
            new_genome.past_code = gen_report["evaluations"][0]["generated_code"]
            issues = "\n- ".join(r["diagnosis"].get("code_issues", ["Unknown issues"]))
            new_genome.critic_feedback = f"Failure type: {r['diagnosis'].get('primary_failure', 'Unknown')}\nIssues:\n- {issues}"
            self.pop_generator = [new_genome]
            return

        if mode == "baseline_c":
            # Random Mutation Ablation: Random parents from viable pool, random mutations.
            new_pop_generator = []
            for _ in range(self.pop_size):
                parent_result = random.choice(results)   # results is now viable only
                parent_genome = parent_result["gen_genome"]
                mutator_genome = parent_result["mut_genome"]
                # Blank diagnosis forces the mutator to act randomly without guided direction
                blank_diagnosis = {"severity": 0.0, "primary_failure": "none", "code_issues": [], "recommended_mutations": []}
                child_genome = self.mutator.propose(blank_diagnosis, parent_genome, mutator_genome)
                child_genome.parent_id = parent_result["index"]
                child_genome.generation_id = generation_id
                new_pop_generator.append(child_genome)
            self.pop_generator = new_pop_generator
            return

        # --- Evolve Mode (Truncation Selection) ---
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

    async def run_eval_only(
        self,
        problems: list[dict],
        genome_config: dict,
        condition_name: str,
    ) -> dict:
        """
        Layer 4 — Held-Out Evaluation.

        Evaluates a single fixed genome against a set of problems without any
        selection or breeding. Used to assess generalization on the held-out
        test set after training is complete.

        Args:
            problems:       List of problem dicts (typically test_problems.json).
            genome_config:  Dict matching GeneratorGenome fields (from best training genome).
            condition_name: Label for the report (e.g. 'baseline_a', 'evolve').

        Returns:
            A structured evaluation report dict.
        """
        genome = GeneratorGenome(**genome_config)
        self.pop_generator = [genome] * self.pop_size
        self.use_validator = False   # eval-only: no LLM validator overhead

        eval_report: dict = {
            "condition": condition_name,
            "genome_config": genome_config,
            "evaluation_start": datetime.utcnow().isoformat(),
            "problems_evaluated": [],
        }

        for problem in problems:
            problem_report = {"problem_id": problem.get("id"), "generations": []}
            results, _ = await self.evaluate_population(0, problem, problem_report)
            passed_count = sum(1 for r in results if r.get("passed_tests", 0) == r.get("total_tests", -1))
            problem_report["solved"] = passed_count > 0
            problem_report["best_fitness"] = max((r["fitness"] for r in results), default=0)
            eval_report["problems_evaluated"].append(problem_report)

        eval_report["evaluation_end"] = datetime.utcnow().isoformat()
        total = len(problems)
        solved = sum(1 for p in eval_report["problems_evaluated"] if p.get("solved"))
        eval_report["summary"] = {
            "total_problems": total,
            "solved": solved,
            "solve_rate": round(solved / max(total, 1), 4),
        }
        return eval_report

    async def run_generations(self, num_generations: int, problems: list[dict], mode: str = "evolve"):
        print(f"--- Starting EvoFlow ({mode.upper()}) with {num_generations} generations on {len(problems)} problems ---")
        # Layer 4: Enable LLM validator only for the full evolutionary run
        self.use_validator = (mode == "evolve")
        self.run_report["mode"] = mode
        
        for problem in problems:
            problem_id = problem.get("id", 0)
            print(f"\n==============================")
            print(f"Evaluating Problem {problem_id}")
            print(f"==============================")
            
            # Reinitialize population for a fresh start on each problem
            self.pop_generator = [GeneratorGenome() for _ in range(self.pop_size)]
            
            problem_report = {
                "problem_id": problem_id,
                "generations": []
            }
            
            for gen in range(num_generations):
                print(f"\n  --- Generation {gen+1}/{num_generations} ---")
                
                results, gen_report = await self.evaluate_population(gen, problem, problem_report)
                
                # Check circuit breaker: If any genome achieves 100% correctness, we found a perfect solution!
                best_fitness = max(r["fitness"] for r in results)
                print(f"  -> Best fitness in Generation {gen+1}: {best_fitness:.2f}")
                
                if any(r.get("passed_tests", 0) == r.get("total_tests", -1) and r.get("total_tests", 0) > 0 for r in results):
                    print(f"  [Circuit Breaker] Perfect correctness reached for Problem {problem_id}. Stopping early.")
                    gen_report["circuit_breaker_triggered"] = True
                    break
                    
                # Otherwise, select and breed
                if gen < num_generations - 1:
                    self.select_and_breed(gen, results, problem_id, gen_report, mode)
                    
            self.run_report["problems_evaluated"].append(problem_report)
            
        # Write the final JSON report at the end of the run
        self._save_structured_report()

