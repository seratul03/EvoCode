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
from src.agents.template import TemplateAgent
from src.agents.hypothesis_engine import HypothesisEngine
from src.canary import CanaryPipeline

from src.genome import AgentGenome, CriticGenome, MutatorGenome, EvaluatorGenome
from src.evolution_trigger import TriggerMonitor
from src.candidate_verifier import CandidateVerifier
from src.arena import ArenaReferee
from src.guarded_selection import GuardedSelector
from src.population import PopulationManager
from src.environment import EnvironmentManager
from src.system_guard import SystemGuard
from src.collaboration import CollaborationManager

from src.orchestration.evaluator import EvoEvaluator
from src.orchestration.breeder import EvoBreeder
from src.orchestration.meta_evolution_runner import MetaEvolutionRunner


class EvoFlowOrchestrator:
    """
    The main orchestrator for the Co-Evolutionary system.
    Manages the 4 populations, runs the generations, and records everything via EventLogger and JSON run logs.
    """
    def __init__(self, pop_size=3, enable_evolution=True, enable_collaboration=True, enable_memory=True, single_agent_mode=False, disable_critic=False, disable_property_testing=False, disable_mutation=False):
        self.client = EvoClient()
        self.logger = EventLogger()
        self.sandbox = Sandbox(timeout_seconds=60)
        self.fitness_scorer = FitnessScorer()
        self.property_tester = PropertyTester()   # Layer 2
        self.trigger_monitor = TriggerMonitor()

        self.enable_evolution = enable_evolution
        self.enable_collaboration = enable_collaboration
        self.enable_memory = enable_memory
        self.single_agent_mode = single_agent_mode
        self.disable_critic = disable_critic
        self.disable_property_testing = disable_property_testing
        self.disable_mutation = disable_mutation

        # 3 distinct base agents for generation
        if self.single_agent_mode:
            self.agent_names = ["Evo_py"]
            self.generators = [
                GeneratorAgent(self.client, language="Python", enable_memory=self.enable_memory)
            ]
        else:
            self.agent_names = ["Evo_py", "Evo_java", "Evo_Cpp"]
            self.generators = [
                GeneratorAgent(self.client, language="Python", enable_memory=self.enable_memory),
                GeneratorAgent(self.client, language="Java", enable_memory=self.enable_memory),
                GeneratorAgent(self.client, language="C++", enable_memory=self.enable_memory)
            ]
        
        # Testing Agent
        from src.agents.tester import TesterAgent
        self.tester = TesterAgent(self.client)

        # Template Agent — isolated call before any generator runs
        self.template_agent = TemplateAgent(self.client)
        
        # Hypothesis Engine
        self.hypothesis_engine = HypothesisEngine(self.client)
        
        # Candidate Verifier (Phase 7)
        self.candidate_verifier = CandidateVerifier()
        
        # Evolution Arena Referee (Phase 8)
        self.arena_referee = ArenaReferee()
        
        # Guarded Selection (Phase 9)
        self.guarded_selector = GuardedSelector()
        
        # Population Manager (Phase 11)
        self.population = PopulationManager()
        
        # Environment Manager (Phase 12)
        self.environment = EnvironmentManager()
        
        # System Guard (Phase 13)
        self.system_guard = SystemGuard(self.population)

        # Collaboration Manager (Phase 15)
        self.collaboration_manager = CollaborationManager(self.client)

        self.validator = CodeValidatorAgent(self.client)
        self.critic = CriticAgent()
        self.mutator = MutatorAgent(self.client)
        self.canary_pipeline = CanaryPipeline(self.client)

        self.pop_size = pop_size 

        # Populations
        self.pop_generator = [AgentGenome() for _ in range(self.pop_size)]
        self.pop_critic = [CriticGenome() for _ in range(self.pop_size)]
        self.pop_mutator = [MutatorGenome() for _ in range(self.pop_size)]
        self.pop_evaluator = [EvaluatorGenome() for _ in range(self.pop_size)]
        
        # Layer 4: validator used only for evolve mode (set in run_generations)
        self.use_validator = True

        # State tracking for the structured JSON report
        self.run_report = {
            "start_time": datetime.utcnow().isoformat(),
            "pop_size": self.pop_size,
            "problems_evaluated": []
        }

        # Sub-modules
        self.evaluator_module = EvoEvaluator(self)
        self.breeder_module = EvoBreeder(self)
        self.meta_evolution_module = MetaEvolutionRunner(self)

    async def _evaluate_single_genome(self, i: int, generation_id: int, problem: dict, problem_id: int, templates: dict | None = None, mode: str = "evolve"):
        return await self.evaluator_module.evaluate_single_genome(i, generation_id, problem, problem_id, templates, mode)

    async def evaluate_population(self, generation_id: int, problem: dict, problem_report: dict, mode: str = "evolve"):
        return await self.evaluator_module.evaluate_population(generation_id, problem, problem_report, mode)

    async def select_and_breed(self, generation_id: int, results: list, problem_id: int, gen_report: dict, mode: str = "evolve"):
        return await self.breeder_module.select_and_breed(results, generation_id, gen_report, mode)

    def _save_structured_report(self):
        self.run_report["end_time"] = datetime.utcnow().isoformat()

        # Support MetaArena subprocess isolation — override report output dir via env var
        report_dir = os.environ.get("EVOCODE_REPORT_DIR", "structured_reports")
        os.makedirs(report_dir, exist_ok=True)

        # Windows doesn't allow colons in filenames. Using dashes.
        # Format: ddmmyyyy_hh-mm-ss
        now = datetime.now()
        filename = now.strftime("%d%m%Y_%H-%M-%S.json")
        filepath = os.path.join(report_dir, filename)

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
        """
        genome = AgentGenome(**genome_config)
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
            results, _ = await self.evaluate_population(0, problem, problem_report, mode="eval_only")
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

    async def run_generations(self, num_generations: int, problems: list[dict], mode: str = "evolve", disable_circuit_breaker: bool = False):
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
            self.pop_generator = [AgentGenome() for _ in range(self.pop_size)]
            
            problem_report = {
                "problem_id": problem_id,
                "generations": []
            }
            
            for gen in range(num_generations):
                print(f"\n  --- Generation {gen+1}/{num_generations} ---")
                
                results, gen_report = await self.evaluate_population(gen, problem, problem_report, mode=mode)
                
                # Calculate population diversity metrics
                import statistics
                fitness_values = [r.get("fitness", 0.0) for r in results]
                if fitness_values:
                    min_fit = min(fitness_values)
                    max_fit = max(fitness_values)
                    mean_fit = statistics.mean(fitness_values)
                    var_fit = statistics.variance(fitness_values) if len(fitness_values) > 1 else 0.0
                    
                    # Add to report
                    gen_report["population_stats"] = {
                        "min_fitness": min_fit,
                        "max_fitness": max_fit,
                        "mean_fitness": mean_fit,
                        "variance": var_fit
                    }
                    
                    # Log to DB
                    self.logger.log_population_stats(problem_id, gen+1, min_fit, max_fit, mean_fit, var_fit)
                
                # Check circuit breaker: If any genome achieves 100% correctness, we found a perfect solution!
                best_fitness = max(r["fitness"] for r in results)
                print(f"  -> Best fitness in Generation {gen+1}: {best_fitness:.2f}")
                
                if not disable_circuit_breaker and any(r.get("passed_tests", 0) == r.get("total_tests", -1) and r.get("total_tests", 0) > 0 for r in results):
                    print(f"  [Circuit Breaker] Perfect correctness reached for Problem {problem_id}. Stopping early.")
                    gen_report["circuit_breaker_triggered"] = True
                    break
                    
                # Otherwise, select and breed
                if gen < num_generations - 1:
                    await self.select_and_breed(gen, results, problem_id, gen_report, mode)
                    
            # After finishing the problem (all generations), feed the best final result to TriggerMonitor
            if results:
                best_final_result = max(results, key=lambda r: r["fitness"])
                agent_id = f"EVO_{best_final_result['language'].upper()}"
                category = problem.get("category", "general")
                
                # --- FINAL EVALUATION ON HIDDEN TEST SET ---
                if mode == "evolve":
                    print(f"\n  --- Final Evaluation on Hidden Test Set ---")
                    code = best_final_result["generated_code"]
                    language = best_final_result["language"]
                    full_base_tests = problem.get("tests", [])
                    
                    import asyncio
                    unique_agent_id = f"prob{problem_id}_final_eval_{agent_id}"
                    try:
                        final_test_results = await asyncio.to_thread(self.sandbox.run, code, full_base_tests, language=language, agent_id=unique_agent_id)
                        final_passed = final_test_results["passed_tests"]
                        final_total = final_test_results["total_tests"]
                        print(f"  [Final Evaluation] {language} Passed {final_passed}/{final_total} tests on the full hidden suite.")
                        
                        problem_report["final_evaluation"] = {
                            "language": language,
                            "passed_tests": final_passed,
                            "total_tests": final_total,
                            "accuracy": final_passed / max(final_total, 1),
                            "crash_tests": len(final_test_results["crash_tests"]),
                            "execution_time_ms": final_test_results["execution_time_ms"],
                            "peak_memory_kb": final_test_results["peak_memory_kb"]
                        }
                        
                        # Update trigger monitor using the FINAL true fitness/passing state
                        is_passed = final_passed == final_total and final_total > 0
                        true_fitness = best_final_result["fitness"] * (final_passed / max(final_total, 1))
                    except Exception as e:
                        print(f"  [Final Evaluation] Failed to run final eval: {e}")
                        is_passed = False
                        true_fitness = 0.0
                else:
                    is_passed = best_final_result.get("passed_tests", 0) == best_final_result.get("total_tests", -1) and best_final_result.get("total_tests", 0) > 0
                    true_fitness = best_final_result["fitness"]

                self.trigger_monitor.add_result(agent_id, category, true_fitness, is_passed)
                should_trigger, reason = self.trigger_monitor.evaluate(agent_id)
                
                if should_trigger and self.enable_evolution:
                    print(f"  [Evolution Trigger] FIRED for {agent_id}! Objective: {reason.get('objective')}")
                    
                    if self.enable_collaboration:
                        advice = await self.collaboration_manager.get_crossover_advice(agent_id, reason)
                        if advice:
                            reason["crossover_advice"] = advice
                    
                    # Phase 14 / Phase 13 integration: Wrap the entire candidate lifecycle in SystemGuard
                    current_genome = best_final_result["gen_genome"]
                    await self.system_guard.execute_with_guards(self, agent_id, reason, current_genome)

                    problem_report["evolution_trigger"] = reason
            
            self.run_report["problems_evaluated"].append(problem_report)
            
        # Write the final JSON report at the end of the run
        self._save_structured_report()

    async def trigger_evolution(self, agent_id: str, reason: dict, current_genome):
        return await self.meta_evolution_module.trigger_evolution(agent_id, reason, current_genome)