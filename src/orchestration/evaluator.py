import asyncio
import ast
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.evoflow import EvoFlowOrchestrator
from src.genome import AgentGenome

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

        if getattr(self.orchestrator, "enable_reviewer", True) and hasattr(self.orchestrator, "reviewer"):
            try:
                review_res = await self.orchestrator.reviewer.review(
                    code, problem, generator.language, gen_genome
                )
                revised = review_res.get("revised_code")
                if revised and revised.strip() != code.strip():
                    issues_str = ", ".join(review_res.get("issues", [])) or "Static improvements"
                    print(f"      [Reviewer] Pre-execution review revised code ({issues_str}).")
                    code = revised
                    safe_revised = code[:100].replace(chr(10), ' ').encode('ascii', 'replace').decode('ascii')
                    print(f"      [Code Revised by Reviewer] (Truncated): {safe_revised}...")
            except Exception as e:
                print(f"      [Reviewer] Review failed ({e}). Proceeding with generated code.")
        
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
            unique_agent_id = f"prob{problem_id}_gen{generation_id}_{agent_name}"
            test_results = await asyncio.to_thread(self.orchestrator.sandbox.run, code, all_tests, language=generator.language, template=template, agent_id=unique_agent_id)
            passed = test_results["passed_tests"]
            total = test_results["total_tests"]
            print(f"      [Sandbox] Passed {passed}/{total} tests (+{len(extra_tests)} ephemeral). Crashes: {len(test_results['crash_tests'])}")

            if test_results["crash_tests"]:
                n_crashes = len(test_results["crash_tests"])
                print(f"      [Evo_fixer] {n_crashes} crash(es) detected. Requesting patch from LLM...")
                fixed_code = await self.orchestrator.evo_fixer.fix(
                    code, test_results, problem, generator.language
                )
                if fixed_code:
                    print(f"      [Evo_fixer] Patch received. Re-evaluating in sandbox...")
                    fixer_agent_id = f"prob{problem_id}_gen{generation_id}_{agent_name}_evofixer"
                    fixed_results = await asyncio.to_thread(
                        self.orchestrator.sandbox.run,
                        fixed_code, all_tests,
                        language=generator.language,
                        template=template,
                        agent_id=fixer_agent_id
                    )
                    fixed_passed = fixed_results["passed_tests"]
                    if fixed_passed > passed:
                        print(f"      [Evo_fixer] \u2705 SUCCESS: {passed} \u2192 {fixed_passed}/{total} tests passed after patch.")
                        code = fixed_code
                        test_results = fixed_results
                        passed = fixed_passed
                        code_hash = hash((generator.language, _normalize_code(code), test_suite_repr))
                    else:
                        print(f"      [Evo_fixer] \u274c Patch did not improve results ({fixed_passed} vs {passed}). Keeping original.")
                else:
                    print(f"      [Evo_fixer] Could not produce a patch. Continuing with original.")

        passed = test_results["passed_tests"]
        total = test_results["total_tests"]

        if passed == total and total > 0 and getattr(self.orchestrator, "enable_optimizer", True) and hasattr(self.orchestrator, "optimizer"):
            try:
                print("      [Optimizer] Code passed all tests. Attempting post-correctness optimization...")
                opt_code = await self.orchestrator.optimizer.optimize(
                    code, problem, generator.language, gen_genome
                )
                if opt_code and opt_code.strip() != code.strip():
                    opt_agent_id = f"prob{problem_id}_gen{generation_id}_{agent_name}_optimized"
                    opt_results = await asyncio.to_thread(
                        self.orchestrator.sandbox.run,
                        opt_code, all_tests,
                        language=generator.language,
                        template=template,
                        agent_id=opt_agent_id
                    )
                    if opt_results.get("passed_tests") == total and len(opt_results.get("crash_tests", [])) == 0:
                        print(f"      [Optimizer] \u2705 SUCCESS: Optimized code verified against test suite ({total}/{total}).")
                        code = opt_code
                        test_results = opt_results
                        passed = test_results["passed_tests"]
                        code_hash = hash((generator.language, _normalize_code(code), test_suite_repr))
                    else:
                        print(f"      [Optimizer] \u274c Optimization broke tests ({opt_results.get('passed_tests')}/{total}). Keeping original code.")
            except Exception as e:
                print(f"      [Optimizer] Optimization failed ({e}). Keeping original code.")
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
            
        return code, test_results, validation, code_hash, False, None

    def _score_and_critique(self, i: int, generation_id: int, problem_id: int, code: str, test_results: dict, validation: dict, code_hash: int, is_cache_hit: bool, cached_data: dict, pop_stats: dict):
        generator = self.orchestrator.generators[i % len(self.orchestrator.generators)]
        gen_genome = self.orchestrator.pop_generator[i]
        crit_genome = self.orchestrator.pop_critic[i]
        mut_genome = self.orchestrator.pop_mutator[i]
        eval_genome = self.orchestrator.pop_evaluator[i]
        
        passed = test_results["passed_tests"]
        total = test_results["total_tests"]
        
        fitness = self.orchestrator.fitness_scorer.calculate_fitness(code, test_results, eval_genome, pop_stats, language=generator.language)
        self.orchestrator.logger.log_fitness("generator", i, generation_id, problem_id, fitness["fitness_value"], fitness)
        
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

        if getattr(self.orchestrator, "enable_architect", True) and hasattr(self.orchestrator, "architect") and "architect_plan" not in problem:
            print("    [ArchitectAgent] Generating algorithmic plan...")
            try:
                rep_genome = self.orchestrator.pop_generator[0] if self.orchestrator.pop_generator else AgentGenome()
                plan = await self.orchestrator.architect.plan(problem, rep_genome)
                problem["architect_plan"] = plan or ""
                if plan:
                    preview = plan.splitlines()[0] if plan else ""
                    print(f"      [Architect] Plan produced: {preview[:80]}...")
            except Exception as e:
                print(f"    [ArchitectAgent] Failed to generate plan: {e}. Continuing without plan.")
                problem["architect_plan"] = ""

        import asyncio
        tasks = [
            self._generate_and_test(i, generation_id, problem, problem_id, templates, mode)
            for i in range(self.orchestrator.pop_size)
        ]
        phase1_results = await asyncio.gather(*tasks)
        
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
                    
        task_outputs = []
        for i in range(self.orchestrator.pop_size):
            code, test_results, validation, code_hash, is_cache_hit, cached_data = phase1_results[i]
            out = self._score_and_critique(i, generation_id, problem_id, code, test_results, validation, code_hash, is_cache_hit, cached_data, pop_stats)
            task_outputs.append(out)

        generation_results = [out[0] for out in task_outputs]
        evaluation_logs = [out[1] for out in task_outputs]
        
        gen_report["evaluations"] = evaluation_logs

        fitnesses = [r.get("fitness", 0.0) for r in generation_results]
        if fitnesses:
            mean_fitness = sum(fitnesses) / len(fitnesses)
            variance = sum((f - mean_fitness) ** 2 for f in fitnesses) / len(fitnesses)
            gen_report["population_diversity"] = {
                "best_fitness": round(max(fitnesses), 6),
                "worst_fitness": round(min(fitnesses), 6),
                "mean_fitness": round(mean_fitness, 6),
                "fitness_variance": round(variance, 6)
            }
        else:
            gen_report["population_diversity"] = {}
            
        problem_report["generations"].append(gen_report)
        return generation_results, gen_report

    async def evaluate_single_genome(self, i: int, generation_id: int, problem: dict, problem_id: int, templates: dict | None = None, mode: str = "evolve"):
        if getattr(self.orchestrator, "enable_architect", True) and hasattr(self.orchestrator, "architect") and "architect_plan" not in problem:
            try:
                rep_genome = self.orchestrator.pop_generator[i] if i < len(self.orchestrator.pop_generator) else AgentGenome()
                plan = await self.orchestrator.architect.plan(problem, rep_genome)
                problem["architect_plan"] = plan or ""
            except Exception:
                problem["architect_plan"] = ""

        phase1_res = await self._generate_and_test(i, generation_id, problem, problem_id, templates, mode)
        code, test_results, validation, code_hash, is_cache_hit, cached_data = phase1_res
        pop_stats = {"min_runtime": 0.0, "max_runtime": 1.0, "min_memory": 0.0, "max_memory": 1.0}
        return self._score_and_critique(i, generation_id, problem_id, code, test_results, validation, code_hash, is_cache_hit, cached_data, pop_stats)

