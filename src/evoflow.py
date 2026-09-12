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

import ast
from src.genome import AgentGenome, CriticGenome, MutatorGenome, EvaluatorGenome
from src.evolution_trigger import TriggerMonitor
from src.clone_manager import CloneManager
from src.candidate_verifier import CandidateVerifier
from src.arena import ArenaReferee
from src.guarded_selection import GuardedSelector, SelectionDecision
from src.memory_manager import MemoryManager, EvolutionEvent
from src.population import PopulationManager
from src.environment import EnvironmentManager
from src.system_guard import SystemGuard
from src.collaboration import CollaborationManager

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
    def __init__(self, pop_size=3, enable_evolution=True, enable_collaboration=True, enable_memory=True, single_agent_mode=False):
        self.client = EvoClient()
        self.logger = EventLogger()
        self.sandbox = Sandbox(timeout_seconds=15)
        self.fitness_scorer = FitnessScorer()
        self.property_tester = PropertyTester()   # Layer 2
        self.trigger_monitor = TriggerMonitor()

        self.enable_evolution = enable_evolution
        self.enable_collaboration = enable_collaboration
        self.enable_memory = enable_memory
        self.single_agent_mode = single_agent_mode

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
        
        self.code_cache = {}

        # Layer 4: validator used only for evolve mode (set in run_generations)
        self.use_validator = True

        # State tracking for the structured JSON report
        self.run_report = {
            "start_time": datetime.utcnow().isoformat(),
            "pop_size": self.pop_size,
            "problems_evaluated": []
        }

    async def _evaluate_single_genome(self, i: int, generation_id: int, problem: dict, problem_id: int, templates: dict | None = None):
        generator = self.generators[i % len(self.generators)]
        agent_name = f"Evo_{generator.language}_{i}"
        print(f"    Evaluating {agent_name} ({generator.language}) - Genome {i+1}/{self.pop_size}...")
        
        gen_genome = self.pop_generator[i]
        crit_genome = self.pop_critic[i]
        mut_genome = self.pop_mutator[i]
        eval_genome = self.pop_evaluator[i]

        # Pick the template for this agent's language (None = no template)
        template = (templates or {}).get(generator.language)

        # 1. Generate
        code = await generator.solve(problem, gen_genome, template=template)
        safe_code = code[:100].replace(chr(10), ' ').encode('ascii', 'replace').decode('ascii')
        print(f"      [Code Generated] (Truncated): {safe_code}...")
        
        # Include language in the cache key so identical code text in different
        # languages doesn't collide, and never let a flaky (non-deterministic)
        # Docker timeout get permanently cached and replayed.
        code_hash = hash((generator.language, _normalize_code(code)))
        if code_hash in self.code_cache:
            print(f"      [CACHE HIT] Generated code is identical to a previous run. Reusing results.")
            cached = self.code_cache[code_hash]
            test_results, validation, fitness, diagnosis = cached["test_results"], cached["validation"], cached["fitness"], cached["diagnosis"]
            passed, total = test_results["passed_tests"], test_results["total_tests"]
            
            # Inject a warning so mutator forces a change if it gets this diagnosis
            # Only inject a warning if the code actually failed some tests
            if passed < total or total == 0 or len(test_results.get("crash_tests", [])) > 0:
                if "break_cache_loop" not in diagnosis.get("recommended_mutations", []):
                    diagnosis.setdefault("recommended_mutations", []).append("break_cache_loop")
                if not any("WARNING: You generated this exact code" in str(iss) for iss in diagnosis.get("code_issues", [])):
                    diagnosis.setdefault("code_issues", []).append("WARNING: You generated this exact code previously and it failed. Try a fundamentally different approach.")
        else:
            # 2. Evo_Tester (Anti-Cheating Check)
            self.tester.language = generator.language
            is_genuine = await self.tester.evaluate(problem, code)
            if not is_genuine:
                print(f"      [Tester] {agent_name} generated INVALID/cheating code. Fitness set to 0.0.")
                test_results = {
                    "passed_tests": 0, "total_tests": len(problem.get("tests", [])),
                    "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
                    "execution_time_ms": 0.0, "peak_memory_kb": 0.0, "test_outputs": [{"status": "crash", "error": "Code rejected by Evo_Tester as hardcoded/cheating."}]
                }
                passed = 0
                total = test_results["total_tests"]
            else:
                # 3. Layer 2 — Property-Based Tests: append ephemeral random cases
                extra_tests = self.property_tester.generate(problem, n=5)
                all_tests = problem.get("tests", []) + extra_tests

                # 4. Sandbox with full test suite (fixed + ephemeral) wrapped in to_thread
                test_results = await asyncio.to_thread(self.sandbox.run, code, all_tests, language=generator.language, template=template, agent_id=f"EVO_{generator.language.upper()}")
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
            
            # Only cache deterministic outcomes (pass/crash). A timeout can be a
            # one-off Docker cold-start fluke rather than a property of the code,
            # so caching it would permanently replay a false failure.
            if len(test_results.get("timeout_tests", [])) == 0:
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

        # Critic Fitness: Correlation with real failure
        if total > 0:
            actual_failure = (passed < total) or len(test_results.get("crash_tests", [])) > 0
            predicted_failure = (severity > 0.5)
            critic_fitness = 1.0 if actual_failure == predicted_failure else -1.0
        else:
            critic_fitness = 0.0

        # Mutator Fitness: Did this genome improve upon its parent?
        mutator_fitness = 0.0
        if gen_genome.parent_id is not None:
            # Child's fitness compared to parent's fitness
            mutator_fitness = fitness["fitness_value"] - gen_genome.parent_fitness

        result_item = {
            "index": i,
            "fitness": fitness["fitness_value"],
            "critic_fitness": critic_fitness,
            "mutator_fitness": mutator_fitness,
            "passed_tests": passed,        # Layer 3A: needed for viability gate
            "total_tests": total,
            "diagnosis": diagnosis,
            "gen_genome": gen_genome,
            "crit_genome": crit_genome,
            "mut_genome": mut_genome,
            "eval_genome": eval_genome,
            "generated_code": code,
            "language": generator.language
        }
        
        evaluation_item = {
            "genome_index": i,
            "gen_genome_snapshot": gen_genome.model_dump(),
            "generated_code": code,
            "test_results": test_results,
            "validation": validation,
            "fitness": fitness,
            "critic_diagnosis": diagnosis
        }
        
        return result_item, evaluation_item

    async def evaluate_population(self, generation_id: int, problem: dict, problem_report: dict):
        problem_id = problem.get("id", 0)

        gen_report = {
            "generation_id": generation_id + 1,
            "evaluations": [],
            "selection_and_breeding": {}
        }

        # ── TemplateAgent: one isolated LLM call before any generator sees anything ──
        # The templates are stored in the problem dict so they survive across generations
        # for the same problem (we don't re-generate them every generation).
        if "templates" not in problem:
            print("    [TemplateAgent] Generating function scaffolds...")
            try:
                problem["templates"] = await self.template_agent.generate(problem)
                for lang, tmpl in problem["templates"].items():
                    preview = tmpl.splitlines()[0] if tmpl else "(empty)"
                    print(f"      [{lang}] {preview}")
            except Exception as e:
                print(f"    [TemplateAgent] Failed to generate templates: {e}. Falling back to no-template mode.")
                problem["templates"] = {}

        templates = problem.get("templates", {})

        task_outputs = []
        for i in range(self.pop_size):
            out = await self._evaluate_single_genome(i, generation_id, problem, problem_id, templates)
            task_outputs.append(out)

        # Separate the results from the evaluation logs
        generation_results = [out[0] for out in task_outputs]
        evaluation_logs = [out[1] for out in task_outputs]
        
        gen_report["evaluations"] = evaluation_logs
            
        problem_report["generations"].append(gen_report)
        return generation_results, gen_report

    async def select_and_breed(self, generation_id: int, results: list, problem_id: int, gen_report: dict, mode: str = "evolve"):
        if mode == "baseline_a":
            # Zero-shot: No feedback, no mutation. Keep same blank slate genomes.
            self.pop_generator = [AgentGenome() for _ in range(self.pop_size)]
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
            new_genome = AgentGenome(**r["gen_genome"].model_dump())
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
                child_genome = await self.mutator.propose(blank_diagnosis, parent_genome, mutator_genome)
                child_genome.parent_id = parent_result["index"]
                child_genome.generation_id = generation_id
                new_pop_generator.append(child_genome)
            self.pop_generator = new_pop_generator
            return

        # --- Evolve Mode (Truncation Selection) ---
        # Truncation selection: Keep top 2, breed 3
        top_k = min(2, len(results))
        top_results = results[:top_k]
        
        # NOTE: slot i is permanently bound to self.generators[i]'s language.
        # Survivors and bred children below are placed back into their ORIGINAL
        # slot index (not appended in fitness-rank order), so a winning genome
        # never drifts into a slot whose language it doesn't match. Cross-language
        # "inspiration" is still carried over via winner_code/winner_language.
        new_pop_generator = [None] * self.pop_size
        new_pop_critic = [None] * self.pop_size
        new_pop_mutator = [None] * self.pop_size
        new_pop_evaluator = [None] * self.pop_size
        
        survivors = [r["index"] for r in top_results]
        killed = [r["index"] for r in results[top_k:]]
        print(f"      Survivors: {survivors} | Killed: {killed}")
        
        gen_report["selection_and_breeding"]["survivors"] = survivors
        gen_report["selection_and_breeding"]["killed"] = killed
        gen_report["selection_and_breeding"]["mutations"] = []
        
        # Sort the results independently to find the best Critic and Mutator!
        top_gen_results = top_results
        
        critic_results = sorted(results, key=lambda x: x["critic_fitness"], reverse=True)
        top_crit_results = critic_results[:top_k] if critic_results else top_results
        
        mutator_results = sorted(results, key=lambda x: x["mutator_fitness"], reverse=True)
        top_mut_results = mutator_results[:top_k] if mutator_results else top_results
        
        # Keep top K, placed back into their ORIGINAL slot index
        for i in range(len(top_results)):
            gen_r = top_gen_results[i]
            slot = gen_r["index"]
            new_pop_generator[slot] = gen_r["gen_genome"]
            self.logger.log_genome("generator", gen_r["index"], generation_id, gen_r["gen_genome"].model_dump(), gen_r["gen_genome"].parent_id or -1)
            
            crit_r = top_crit_results[i % len(top_crit_results)]
            new_pop_critic[slot] = crit_r["crit_genome"]
            
            mut_r = top_mut_results[i % len(top_mut_results)]
            new_pop_mutator[slot] = mut_r["mut_genome"]
            
            new_pop_evaluator[slot] = gen_r["eval_genome"]
            
        # Breed to fill the remaining (killed) slots, each keeping its own language
        empty_slots = [s for s in range(self.pop_size) if new_pop_generator[s] is None]
        for n, child_index in enumerate(empty_slots):
            
            # Pick parents from the top K
            parent_gen_result = top_gen_results[n % len(top_gen_results)]
            parent_crit_result = top_crit_results[n % len(top_crit_results)]
            parent_mut_result = top_mut_results[n % len(top_mut_results)]
            
            parent_genome = parent_gen_result["gen_genome"]
            mutator_genome = parent_mut_result["mut_genome"]
            diagnosis = parent_gen_result["diagnosis"]
            
            target_language = self.generators[child_index % len(self.generators)].language
            
            # Identify the absolute winner (highest fitness overall)
            winner_result = top_gen_results[0]
            winner_code = winner_result.get("generated_code")
            winner_language = winner_result.get("language")
            
            # Use Mutator to propose new genome
            child_genome = await self.mutator.propose(
                diagnosis, 
                parent_genome, 
                mutator_genome,
                winner_code=winner_code,
                winner_language=winner_language,
                target_language=target_language
            )
            
            # Validate proposed genome using Canary Pipeline
            is_valid = await self.canary_pipeline.validate_mutation(child_genome, language=target_language)
            
            if not is_valid:
                print(f"      [Breeding] Canary validation failed. Rejecting mutation and keeping parent genome.")
                child_genome = parent_genome.model_copy(deep=True)
                
            child_genome.parent_id = parent_gen_result["index"]
            child_genome.parent_fitness = parent_gen_result["fitness"]
            child_genome.generation_id = generation_id
            
            new_pop_generator[child_index] = child_genome
            
            # Mutate non-generator genomes, placed into the same slot
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
            print(f"        Changes: {child_genome.model_dump()}")
            
            gen_report["selection_and_breeding"]["mutations"].append({
                "parent_index": parent_gen_result["index"],
                "child_index": child_index,
                "parent_genome": parent_genome.model_dump(),
                "child_genome": child_genome.model_dump()
            })
            
            # Log mutation
            self.logger.log_mutation(
                "generator", child_index, generation_id,
                parent_genome.model_dump(), child_genome.model_dump(),
                "critic_guided", "breeding", parent_gen_result["fitness"], 0.0
            )
            
        self.pop_generator = new_pop_generator
        self.pop_critic = new_pop_critic
        self.pop_mutator = new_pop_mutator
        self.pop_evaluator = new_pop_evaluator

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

        Evaluates a single fixed genome against a set of problems without any
        selection or breeding. Used to assess generalization on the held-out
        test set after training is complete.

        Args:
            problems:       List of problem dicts (typically test_problems.json).
            genome_config:  Dict matching AgentGenome fields (from best training genome).
            condition_name: Label for the report (e.g. 'baseline_a', 'evolve').

        Returns:
            A structured evaluation report dict.
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
                
                results, gen_report = await self.evaluate_population(gen, problem, problem_report)
                
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
                is_passed = best_final_result.get("passed_tests", 0) == best_final_result.get("total_tests", -1) and best_final_result.get("total_tests", 0) > 0
                agent_id = f"EVO_{best_final_result['language'].upper()}"
                category = problem.get("category", "general")
                
                self.trigger_monitor.add_result(agent_id, category, best_final_result["fitness"], is_passed)
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
        """
        Executes a single evolutionary cycle (Phases 5-10) for the given agent.
        This is wrapped by SystemGuard to safely rollback in case of critical failure.
        """
        # Phase 5: Formulate hypothesis
        print(f"  [HypothesisEngine] Formulating hypothesis for {agent_id}...")
        hypothesis = await self.hypothesis_engine.generate_hypothesis(agent_id, reason, current_genome)
        print(f"  [HypothesisEngine] Output: {hypothesis}")
        reason["hypothesis_data"] = hypothesis

        # Phase 6: Create candidate clone
        try:
            clone = CloneManager.create_candidate(agent_id, current_genome, hypothesis)
            print(f"  [CloneManager] Candidate '{clone.candidate_id}' created. Diff: {list(clone.diff.keys())}")

            # Phase 7: Verify candidate before staging
            promoted = CloneManager.commit_candidate(clone, verifier=self.candidate_verifier)
            verification = clone.workspace_path  # metadata.json was updated in place
            # Re-read verification result from metadata
            import json as _json
            meta_path = os.path.join(clone.workspace_path, "metadata.json")
            verification_data = {}
            if os.path.exists(meta_path):
                with open(meta_path) as _f:
                    verification_data = _json.load(_f).get("verification", {})

            reason["candidate"] = {
                "candidate_id": clone.candidate_id,
                "workspace": clone.workspace_path,
                "parent_hash": clone.parent_hash,
                "candidate_hash": clone.candidate_hash,
                "diff": clone.diff,
                "verification": verification_data,
                "promoted": promoted is not None,
            }
            if promoted:
                print(f"  [Verifier] Candidate '{clone.candidate_id}' PASSED all stages. Staged for arena.")
                # Phase 8: The Arena
                print(f"  [Arena] Refereeing competition between {clone.parent_hash[:8]} and {clone.candidate_hash[:8]} at Pressure Level {self.environment.profile.level}...")
                arena = ArenaReferee()
                arena_result = arena.compare(
                    clone.parent_genome,
                    clone.candidate_genome,
                    env_profile=self.environment.profile
                )
                print(f"  [Arena] Winner: {arena_result.winner.upper()} (Margin: {arena_result.margin:.4f})")
                reason["candidate"]["arena_result"] = arena_result.to_dict()
                
                # Phase 9: Guarded Selection
                decision, decision_reason = self.guarded_selector.evaluate(arena_result)
                print(f"  [GuardedSelection] Decision: {decision.name} - {decision_reason}")
                reason["candidate"]["selection_decision"] = decision.name
                reason["candidate"]["selection_reason"] = decision_reason
                
                if decision == SelectionDecision.PROMOTE:
                    if self.population.is_duplicate(clone.candidate_hash):
                        print(f"  [Population] Candidate '{clone.candidate_id}' is a duplicate. Discarding to maintain diversity.")
                        CloneManager.discard_candidate(clone)
                        decision_reason += " (Discarded by PopulationManager: Duplicate)"
                    else:
                        print(f"  [EvoFlow] Promoting candidate '{clone.candidate_id}' to a new agent in the population!")
                        new_agent_id = CloneManager.fork_to_new_agent(clone)
                        self.population.register_agent(new_agent_id, clone.candidate_hash)
                        
                        # Collect active population fitness scores for limit enforcement and environment adaptation
                        mock_scores = {aid: arena_result.parent_score for aid in self.population.active_agents}
                        mock_scores[new_agent_id] = arena_result.candidate_score
                        
                        self.population.enforce_population_limit(mock_scores)
                        print(f"  [Population] Spawned {new_agent_id}. Active agents: {len(self.population.active_agents)}")
                        
                        self.environment.evaluate_pressure(mock_scores)
                else:
                    print(f"  [EvoFlow] Discarding candidate '{clone.candidate_id}'.")
                    CloneManager.discard_candidate(clone)
                    
                # Phase 10: Record the Evolution Event
                import os, json
                meta_path = os.path.join(clone.workspace_path, "metadata.json")
                verification_data = {}
                if os.path.exists(meta_path):
                    with open(meta_path) as _f:
                        verification_data = json.load(_f).get("verification", {})
                
                event = EvolutionEvent.create(
                    agent_id=agent_id,
                    generation=0,
                    trigger_data=reason,
                    hypothesis_data=hypothesis,
                    parent_hash=clone.parent_hash,
                    candidate_hash=clone.candidate_hash,
                    diff=clone.diff,
                    verification_result=verification_data,
                    arena_result=arena_result.to_dict(),
                    selection_decision=decision.name,
                    selection_reason=decision_reason
                )
                MemoryManager.record_event(event)
                print(f"  [Memory] Evolution event '{event.event_id}' recorded.")
                
            else:
                print(f"  [Verifier] Candidate '{clone.candidate_id}' failed verification. Discarded.")
                CloneManager.discard_candidate(clone)

        except Exception as e:
            print(f"  [CloneManager] Error during cloning/mutation: {e}")
            import traceback
            traceback.print_exc()
            raise e