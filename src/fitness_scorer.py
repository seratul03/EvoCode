from src.agents.evaluators import (
    CorrectnessEvaluator,
    RuntimeEvaluator,
    MemoryEvaluator,
    CodeEfficiencyEvaluator,
    ComplexityEvaluator,
    RobustnessEvaluator
)
from src.genome import EvaluatorGenome

class FitnessScorer:
    """
    Aggregates scores from the 6 evaluators into a single fitness value.
    Weights are fixed per the design report.
    """
    def __init__(self):
        self.correctness = CorrectnessEvaluator()
        self.runtime = RuntimeEvaluator()
        self.memory = MemoryEvaluator()
        self.efficiency = CodeEfficiencyEvaluator()
        self.complexity = ComplexityEvaluator()
        self.robustness = RobustnessEvaluator()

        self.weights = {
            "correctness": 0.50,
            "runtime": 0.15,
            "memory": 0.10,
            "efficiency": 0.10,
            "complexity": 0.10,
            "robustness": 0.05
        }

    def calculate_fitness(self, code: str, test_results: dict, genome: EvaluatorGenome) -> dict:
        """
        Calculates fitness score and returns the breakdown.
        """
        scores = {
            "correctness": self.correctness.score(test_results, genome),
            "runtime": self.runtime.score(test_results, genome),
            "memory": self.memory.score(test_results, genome),
            "efficiency": self.efficiency.score(code, test_results, genome),
            "complexity": self.complexity.score(code, genome),
            "robustness": self.robustness.score(code, genome)
        }

        total_fitness = sum(scores[key] * self.weights[key] for key in self.weights)
        
        return {
            "fitness_value": total_fitness,
            "breakdown": scores
        }
