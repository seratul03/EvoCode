from src.client import EvoClient
from src.agents.generator import GeneratorAgent
from src.genome import GeneratorGenome
from src.sandbox import Sandbox

class BaselineRunner:
    """
    Runner for the Baseline Conditions (A, B, C).
    Condition A: Single Generator, 3 iterations
    Condition B: Single Generator, 10 iterations (matched budget)
    Condition C: Random genome variation, no selection
    """
    def __init__(self):
        self.client = EvoClient()
        self.generator = GeneratorAgent(self.client)
        self.sandbox = Sandbox()

    async def run_baseline_a(self, problems: list[dict]):
        print("Running Baseline A (3 iterations)...")
        genome = GeneratorGenome()
        for problem in problems:
            for iteration in range(3):
                code = await self.generator.solve(problem, genome)
                results = self.sandbox.run(code, problem.get("tests", []))
                if results["passed_tests"] == results["total_tests"] and results["total_tests"] > 0:
                    print(f"Problem {problem.get('id')} solved at iteration {iteration}")
                    break

    async def run_baseline_b(self, problems: list[dict]):
        print("Running Baseline B (10 iterations)...")
        genome = GeneratorGenome()
        for problem in problems:
            for iteration in range(10):
                code = await self.generator.solve(problem, genome)
                results = self.sandbox.run(code, problem.get("tests", []))
                if results["passed_tests"] == results["total_tests"] and results["total_tests"] > 0:
                    print(f"Problem {problem.get('id')} solved at iteration {iteration}")
                    break

    async def run_baseline_c(self, problems: list[dict]):
        print("Running Baseline C (Random Mutation)...")
        import random
        for problem in problems:
            for iteration in range(10): # matched attempts
                # Random genome
                genome = GeneratorGenome(
                    temperature=random.random(),
                    prompt_style=random.choice(["direct", "chain_of_thought", "test_first", "step_by_step"])
                )
                code = await self.generator.solve(problem, genome)
                results = self.sandbox.run(code, problem.get("tests", []))
                if results["passed_tests"] == results["total_tests"] and results["total_tests"] > 0:
                    print(f"Problem {problem.get('id')} solved at iteration {iteration}")
                    break
