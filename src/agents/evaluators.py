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
        exec_ms = test_results.get("execution_time_ms", 0.0)
        if exec_ms <= 0: return 1.0
        
        if pop_stats and "max_runtime" in pop_stats and "min_runtime" in pop_stats and pop_stats["max_runtime"] > pop_stats["min_runtime"]:
            min_r = pop_stats["min_runtime"]
            max_r = pop_stats["max_runtime"]
            score = 1.0 - ((exec_ms - min_r) / (max_r - min_r))
        else:
            score = 1.0 - (exec_ms / 1000.0)
            
        return max(0.0, min(1.0, score * genome.sensitivity))

class MemoryEvaluator(Evaluator):
    def score(self, test_results: dict, genome: EvaluatorGenome, pop_stats: dict = None) -> float:
        mem_kb = test_results.get("peak_memory_kb", 0.0)
        if mem_kb <= 0: return 1.0
        
        if pop_stats and "max_memory" in pop_stats and "min_memory" in pop_stats and pop_stats["max_memory"] > pop_stats["min_memory"]:
            min_m = pop_stats["min_memory"]
            max_m = pop_stats["max_memory"]
            score = 1.0 - ((mem_kb - min_m) / (max_m - min_m))
        else:
            score = 1.0 - (mem_kb / 50000.0)
            
        return max(0.0, min(1.0, score * genome.sensitivity))

class CodeEfficiencyEvaluator(Evaluator):
    def score(self, code: str, test_results: dict, genome: EvaluatorGenome) -> float:
        if test_results["total_tests"] == 0:
            return 0.0
        passed = test_results["passed_tests"]
        return min(1.0, (passed / test_results["total_tests"]) * genome.sensitivity)

class ComplexityEvaluator(Evaluator):
    def score(self, code: str, genome: EvaluatorGenome | None = None, language: str = "Python") -> float:
        lang = (language or "Python").strip().lower()
        total_cc = 1
        try:
            if lang in ("python", "py"):
                try:
                    import radon.complexity as radon_cc
                    blocks = radon_cc.cc_visit(code)
                    total_cc = sum(block.complexity for block in blocks) or 1
                except Exception:
                    total_cc = self._calculate_lizard_cc(code, "solution.py")
            elif lang in ("java",):
                total_cc = self._calculate_lizard_cc(code, "Solution.java")
            elif lang in ("c++", "cpp", "c"):
                total_cc = self._calculate_lizard_cc(code, "solution.cpp")
            else:
                total_cc = self._calculate_lizard_cc(code, f"solution.{lang}")

            score = 1.0 - (total_cc / 20.0)
            sensitivity = getattr(genome, "sensitivity", 1.0)
            return max(0.0, min(1.0, score * sensitivity))
        except Exception:
            return 1.0

    def _calculate_lizard_cc(self, code: str, filename: str) -> int:
        try:
            import lizard
            res = lizard.analyze_file.analyze_source_code(filename, code)
            cc_list = [f.cyclomatic_complexity for f in res.function_list]
            if cc_list:
                return sum(cc_list)
        except Exception:
            pass
        return self._fallback_cyclomatic_complexity(code)

    def _fallback_cyclomatic_complexity(self, code: str) -> int:
        """Lexical decision-point fallback: counts branches (if, for, while, catch, case, &&, ||, ?) + 1."""
        patterns = [
            r'\bif\b',
            r'\bfor\b',
            r'\bwhile\b',
            r'\bcase\b',
            r'\bcatch\b',
            r'&&',
            r'\|\|',
            r'\?',
            r'\belif\b',
        ]
        count = 1
        for pat in patterns:
            count += len(re.findall(pat, code))
        return count

class RobustnessEvaluator(Evaluator):
    def score(self, code: str, genome: EvaluatorGenome | None = None, language: str = "Python") -> float:
        score = 0.0
        lang = (language or "Python").strip().lower()
        if lang in ("python", "py"):
            if "try:" in code or "except " in code:
                score += 0.5
            if re.search(r"if.*(?:==|!=|>|<|is).*(?:None|0|\[\]|\'\')", code):
                score += 0.5
        else:
            if "try" in code and ("catch" in code or "except" in code):
                score += 0.5
            if re.search(r"if.*(?:==|!=|>|<).*(?:null|nullptr|NULL|0|empty|isEmpty)", code, re.IGNORECASE):
                score += 0.5
        sensitivity = getattr(genome, "sensitivity", 1.0)
        return min(1.0, score * sensitivity)

