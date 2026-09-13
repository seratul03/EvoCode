from src.genome import EvaluatorGenome
import ast
import re

class Evaluator:
    """Base class for all evaluators."""
    def __init__(self):
        pass

class CorrectnessEvaluator(Evaluator):
    def score(self, test_results: dict, genome: EvaluatorGenome) -> float:
        if test_results["total_tests"] == 0:
            return 0.0
        base_score = test_results["passed_tests"] / test_results["total_tests"]
        return min(1.0, base_score * genome.sensitivity)

class RuntimeEvaluator(Evaluator):
    def score(self, test_results: dict, genome: EvaluatorGenome, pop_stats: dict = None) -> float:
        exec_ms = test_results["execution_time_ms"]
        if exec_ms <= 0: return 1.0
        
        if pop_stats and "max_runtime" in pop_stats and "min_runtime" in pop_stats and pop_stats["max_runtime"] > pop_stats["min_runtime"]:
            min_r = pop_stats["min_runtime"]
            max_r = pop_stats["max_runtime"]
            score = 1.0 - ((exec_ms - min_r) / (max_r - min_r))
        else:
            # Fallback
            score = 1.0 - (exec_ms / 1000.0)
            
        return max(0.0, min(1.0, score * genome.sensitivity))

class MemoryEvaluator(Evaluator):
    def score(self, test_results: dict, genome: EvaluatorGenome, pop_stats: dict = None) -> float:
        mem_kb = test_results["peak_memory_kb"]
        if mem_kb <= 0: return 1.0
        
        if pop_stats and "max_memory" in pop_stats and "min_memory" in pop_stats and pop_stats["max_memory"] > pop_stats["min_memory"]:
            min_m = pop_stats["min_memory"]
            max_m = pop_stats["max_memory"]
            score = 1.0 - ((mem_kb - min_m) / (max_m - min_m))
        else:
            # Fallback
            score = 1.0 - (mem_kb / 50000.0) # 50MB arbitrary max
            
        return max(0.0, min(1.0, score * genome.sensitivity))

class CodeEfficiencyEvaluator(Evaluator):
    def score(self, code: str, test_results: dict, genome: EvaluatorGenome) -> float:
        # Removed lines of code bias to ensure fair evaluation across Python, Java, and C++
        if test_results["total_tests"] == 0:
            return 0.0
        passed = test_results["passed_tests"]
        return min(1.0, (passed / test_results["total_tests"]) * genome.sensitivity)

class ComplexityEvaluator(Evaluator):
    def score(self, code: str, genome: EvaluatorGenome) -> float:
        try:
            import radon.complexity as radon_cc
            blocks = radon_cc.cc_visit(code)
            total_cc = sum(block.complexity for block in blocks)
            # CC > 10 is complex. We want to penalize high CC.
            score = 1.0 - (total_cc / 20.0)
            return max(0.0, min(1.0, score * genome.sensitivity))
        except Exception:
            # For Java, C++ or if radon fails, return 1.0 so they aren't penalized
            return 1.0

class RobustnessEvaluator(Evaluator):
    def score(self, code: str, genome: EvaluatorGenome) -> float:
        score = 0.0
        # Simple heuristics for robustness
        if "try:" in code or "except " in code:
            score += 0.5
        if re.search(r"if.*(?:==|!=|>|<|is).*(?:None|0|\[\]|\'\')", code):
            score += 0.5 # boundary checks
        return min(1.0, score * genome.sensitivity)
