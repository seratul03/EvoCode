import asyncio
import ast
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.evoflow import EvoFlowOrchestrator

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

class EvoEvaluator:
    def __init__(self, orchestrator: 'EvoFlowOrchestrator'):
        self.orchestrator = orchestrator


    async def _generate_and_test(self, i: int, generation_id: int, problem: dict, problem_id: int, templates: dict | None = None, mode: str = "evolve"):
        generator = self.orchestrator.generators[i % len(self.orchestrator.generators)]
        agent_name = f"Evo_{generator.language}_{i}"
        print(f"    Evaluating {agent_name} ({generator.language}) - Genome {i+1}/{self.orchestrator.pop_size}...")
        
        gen_genome = self.orchestrator.pop_generator[i]
        template = (templates or {}).get(generator.language)

        code = await generator.solve(problem, gen_genome, template=template)
        safe_code = code[:100].replace(chr(10), ' ').encode('ascii', 'replace').decode('ascii')
        print(f"      [Code Generated] (Truncated): {safe_code}...")
        
        problem_tests = problem.get("tests", [])
        if mode == "evolve":
            split_idx = max(1, len(problem_tests) * 8 // 10)
            base_tests = problem_tests[:split_idx]
        else:
            base_tests = problem_tests
            
        if getattr(self.orchestrator, "disable_property_testing", False):
            extra_tests = []
            print("      [Ablation] Property Tester disabled. Using base tests only.")
        else:
            extra_tests = self.orchestrator.property_tester.generate(problem, n=5)
        
        all_tests = base_tests + extra_tests
        test_suite_repr = repr([(t.get("input"), t.get("expected")) for t in all_tests])
        
        code_hash = hash((generator.language, _normalize_code(code), test_suite_repr))
        
        is_cache_hit = False
        cached_data = None
        test_results = None
        validation = None
        
        if code_hash in self.orchestrator.code_cache:
            print(f"      [CACHE HIT] Generated code is identical to a previous run. Reusing results.")
            cached_data = self.orchestrator.code_cache[code_hash]
            is_cache_hit = True
            test_results = cached_data["test_results"]
            validation = cached_data["validation"]
        else:
            self.orchestrator.tester.language = generator.language
            is_genuine = await self.orchestrator.tester.evaluate(problem, code)
            if not is_genuine:
                print(f"      [Tester] {agent_name} generated INVALID/cheating code. Fitness set to 0.0.")
                test_results = {
                    "passed_tests": 0, "total_tests": len(all_tests),
                    "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
                    "execution_time_ms": 0.0, "peak_memory_kb": 0.0, "test_outputs": [{"status": "crash", "error": "Code rejected by Evo_Tester as hardcoded/cheating."}]
                }
            else:
                import asyncio
                test_results = await asyncio.to_thread(self.orchestrator.sandbox.run, code, all_tests, language=generator.language, template=template, agent_id=f"EVO_{generator.language.upper()}")
                passed = test_results["passed_tests"]
                total = test_results["total_tests"]
                print(f"      [Sandbox] Passed {passed}/{total} tests (+{len(extra_tests)} ephemeral). Crashes: {len(test_results['crash_tests'])}")

            passed = test_results["passed_tests"]
            total = test_results["total_tests"]
            self.orchestrator.logger.log_test_result(
                problem_id, generation_id, i,
                passed, total,
                test_results["failed_test_ids"], test_results["timeout_tests"],
                test_results["crash_tests"], test_results["execution_time_ms"],
                test_results["peak_memory_kb"]
            )

            if self.orchestrator.use_validator:
                validation = await self.orchestrator.validator.validate(code, problem, test_results)
            else:
                validation = {
                    "is_correct": passed == total and total > 0,
                    "confidence": passed / max(total, 1),
                    "issues": [] if passed == total else [f"Failed {total - passed}/{total} tests."]
                }
            self.orchestrator.logger.log_validation(
                problem_id, generation_id, validation.get("is_correct", False),
                validation.get("confidence", 0.0), str(validation.get("issues", [])), 0
            )

        return code, test_results, validation, code_hash, is_cache_hit, cached_data

    def _score_and_critique(self, i: int, generation_id: int, problem_id: int, code: str, test_results: dict, validation: dict, code_hash: int, is_cache_hit: bool, cached_data: dict, pop_stats: dict):
        generator = self.orchestrator.generators[i % len(self.orchestrator.generators)]
        gen_genome = self.orchestrator.pop_generator[i]
        crit_genome = self.orchestrator.pop_critic[i]
        mut_genome = self.orchestrator.pop_mutator[i]
        eval_genome = self.orchestrator.pop_evaluator[i]
        
        passed = test_results["passed_tests"]
        total = test_results["total_tests"]
        
        fitness = self.orchestrator.fitness_scorer.calculate_fitness(code, test_results, eval_genome, pop_stats)
        self.orchestrator.logger.log_fitness("generator", i, generation_id, problem_id, fitness["fitness_value"], fitness)
        
        if is_cache_hit:
            diagnosis = cached_data["diagnosis"]
            if passed < total or total == 0 or len(test_results.get("crash_tests", [])) > 0:
                if "break_cache_loop" not in diagnosis.get("recommended_mutations", []):
                    diagnosis.setdefault("recommended_mutations", []).append("break_cache_loop")
                if not any("WARNING: You generated this exact code" in str(iss) for iss in diagnosis.get("code_issues", [])):
                    diagnosis.setdefault("code_issues", []).append("WARNING: You generated this exact code previously and it failed. Try a fundamentally different approach.")
        else:
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
            elif getattr(self.orchestrator, "disable_critic", False):
                diagnosis = {
                    "severity": 0.5,
                    "primary_failure": "ablation_mode",
                    "code_issues": ["Critic disabled"],
                    "recommended_mutations": []
                }
                print("      [Ablation] Critic disabled. Returning generic diagnosis.")
            else:
                diagnosis = self.orchestrator.critic.critique(code, test_results, validation, crit_genome)
            
            if len(test_results.get("timeout_tests", [])) == 0:
                self.orchestrator.code_cache[code_hash] = {
                    "test_results": test_results,
                    "validation": validation,
                    "fitness": fitness,
                    "diagnosis": diagnosis
                }
                
        severity = diagnosis.get("severity", 0.0)
        primary_fail = diagnosis.get("primary_failure", "none")
        rec_mutations = diagnosis.get("recommended_mutations", [])
        print(f"      [Critic] Severity: {severity:.2f}, Failure: {primary_fail}, Mutations: {rec_mutations}")
        print(f"      [Fitness] Score: {fitness['fitness_value']:.4f} (correctness={fitness.get('correctness_rate', passed/max(total,1)):.2f} x quality={fitness.get('quality_score', 0):.2f})")

        self.orchestrator.logger.log_critic(
            problem_id, generation_id, primary_fail,
            severity, diagnosis.get("code_issues", []), rec_mutations
        )

        if total > 0:
            actual_failure = (passed < total) or len(test_results.get("crash_tests", [])) > 0
            predicted_failure = (severity > 0.5)
            critic_fitness = 1.0 if actual_failure == predicted_failure else -1.0
        else:
            critic_fitness = 0.0

        mutator_fitness = 0.0
        if gen_genome.parent_id is not None:
            mutator_fitness = fitness["fitness_value"] - gen_genome.parent_fitness

        result_item = {
            "index": i,
            "fitness": fitness["fitness_value"],
            "critic_fitness": critic_fitness,
            "mutator_fitness": mutator_fitness,
            "passed_tests": passed,
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


    async def evaluate_population(self, generation_id: int, problem: dict, problem_report: dict, mode: str = "evolve"):
        problem_id = problem.get("id", 0)

        gen_report = {
            "generation_id": generation_id + 1,
            "evaluations": [],
            "selection_and_breeding": {}
        }

        if "templates" not in problem:
            print("    [TemplateAgent] Generating function scaffolds...")
            try:
                problem["templates"] = await self.orchestrator.template_agent.generate(problem)
                for lang, tmpl in problem["templates"].items():
                    preview = tmpl.splitlines()[0] if tmpl else "(empty)"
                    print(f"      [{lang}] {preview}")
            except Exception as e:
                print(f"    [TemplateAgent] Failed to generate templates: {e}. Falling back to no-template mode.")
                problem["templates"] = {}

        templates = problem.get("templates", {})

        task_outputs = []
        phase1_results = []
        for i in range(self.orchestrator.pop_size):
            out = await self._generate_and_test(i, generation_id, problem, problem_id, templates, mode)
            phase1_results.append(out)
            
        pop_stats = {
            "min_runtime": float('inf'),
            "max_runtime": -1.0,
            "min_memory": float('inf'),
            "max_memory": -1.0
        }
        for res in phase1_results:
            tr = res[1]
            if tr:
                rt = tr.get("execution_time_ms", 0.0)
                mem = tr.get("peak_memory_kb", 0.0)
                if rt > 0:
                    pop_stats["min_runtime"] = min(pop_stats["min_runtime"], rt)
                    pop_stats["max_runtime"] = max(pop_stats["max_runtime"], rt)
                if mem > 0:
                    pop_stats["min_memory"] = min(pop_stats["min_memory"], mem)
                    pop_stats["max_memory"] = max(pop_stats["max_memory"], mem)
                    
        for i in range(self.orchestrator.pop_size):
            code, test_results, validation, code_hash, is_cache_hit, cached_data = phase1_results[i]
            out = self._score_and_critique(i, generation_id, problem_id, code, test_results, validation, code_hash, is_cache_hit, cached_data, pop_stats)
            task_outputs.append(out)

        generation_results = [out[0] for out in task_outputs]
        evaluation_logs = [out[1] for out in task_outputs]
        
        gen_report["evaluations"] = evaluation_logs
            
        problem_report["generations"].append(gen_report)
        return generation_results, gen_report
