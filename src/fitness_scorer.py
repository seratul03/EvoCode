from src.agents.evaluators import (
    RuntimeEvaluator,
    MemoryEvaluator,
    CodeEfficiencyEvaluator,
    ComplexityEvaluator,
    RobustnessEvaluator,
)
from src.genome import EvaluatorGenome


class FitnessScorer:
    """
    Layer 3B — Multiplicative Fitness.

    Formula:
        correctness_rate = passed_tests / total_tests
        quality_score    = weighted sum of runtime, memory, efficiency, complexity, robustness
        fitness_value    = correctness_rate * quality_score

    If correctness_rate == 0 (zero tests passed), fitness_value is ALWAYS 0.0.
    No quality signal — no matter how clean or fast the code — can compensate
    for failing every test. This is the LeetCode rule: wrong answer = 0 points.
    """

    # Quality sub-weights (sum to 1.0)
    QUALITY_WEIGHTS = {
        "runtime":    0.30,
        "memory":     0.20,
        "efficiency": 0.20,
        "complexity": 0.20,
        "robustness": 0.10,
    }

    def __init__(self):
        self.runtime    = RuntimeEvaluator()
        self.memory     = MemoryEvaluator()
        self.efficiency = CodeEfficiencyEvaluator()
        self.complexity = ComplexityEvaluator()
        self.robustness = RobustnessEvaluator()

    def calculate_fitness(self, code: str, test_results: dict, genome: EvaluatorGenome) -> dict:
        """
        Returns a dict with 'fitness_value' (float in [0, 1]) and 'breakdown' (dict).

        breakdown includes:
          - correctness_rate : raw pass-rate (0.0 to 1.0)
          - quality_score    : blended quality before gating
          - fitness_value    : final score after multiplicative gate
          - plus individual sub-scores for logging
        """
        total = max(test_results.get("total_tests", 1), 1)
        passed = test_results.get("passed_tests", 0)
        correctness_rate = passed / total

        quality_scores = {
            "runtime":    self.runtime.score(test_results, genome),
            "memory":     self.memory.score(test_results, genome),
            "efficiency": self.efficiency.score(code, test_results, genome),
            "complexity": self.complexity.score(code, genome),
            "robustness": self.robustness.score(code, genome),
        }

        quality_score = sum(
            quality_scores[k] * self.QUALITY_WEIGHTS[k]
            for k in self.QUALITY_WEIGHTS
        )

        # --- THE GATE ---
        # Zero correctness collapses the entire fitness to 0.
        fitness_value = correctness_rate * quality_score

        return {
            "fitness_value": round(fitness_value, 6),
            "correctness_rate": round(correctness_rate, 4),
            "quality_score": round(quality_score, 4),
            "breakdown": {
                "correctness": round(correctness_rate, 4),
                **{k: round(v, 4) for k, v in quality_scores.items()},
            },
        }
