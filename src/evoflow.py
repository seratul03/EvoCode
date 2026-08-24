import asyncio
from src.client import EvoClient
from src.event_logger import EventLogger
from src.sandbox import Sandbox
from src.fitness_scorer import FitnessScorer

from src.agents.generator import GeneratorAgent
from src.agents.code_validator import CodeValidatorAgent
from src.agents.critic import CriticAgent
from src.agents.mutator import MutatorAgent

from src.genome import GeneratorGenome, CriticGenome, MutatorGenome, EvaluatorGenome

class EvoFlowOrchestrator:
    """
    The main orchestrator for the Co-Evolutionary system.
    Manages the 4 populations, runs the generations, and records everything via EventLogger.
    """
    def __init__(self):
        self.client = EvoClient()
        self.logger = EventLogger()
        self.sandbox = Sandbox(timeout_seconds=5)
        self.fitness_scorer = FitnessScorer()
        
        # Agents
        self.generator = GeneratorAgent(self.client)
        self.validator = CodeValidatorAgent(self.client)
        self.critic = CriticAgent()
        self.mutator = MutatorAgent()

        # Populations
        self.pop_generator = [GeneratorGenome() for _ in range(5)]
        self.pop_critic = [CriticGenome() for _ in range(3)]
        self.pop_mutator = [MutatorGenome() for _ in range(3)]
        self.pop_evaluator = [EvaluatorGenome() for _ in range(6)]

    async def run_generation(self, generation_id: int, problems: list[dict]):
        print(f"--- Starting Generation {generation_id} ---")
        
        for problem in problems:
            problem_id = problem.get("id", 0)
            
            # Simplified for now: just evaluate the first genome of each population
            gen_genome = self.pop_generator[0]
            crit_genome = self.pop_critic[0]
            mut_genome = self.pop_mutator[0]
            eval_genome = self.pop_evaluator[0]

            # 1. Execute
            code = await self.generator.solve(problem, gen_genome)
            
            # 2. Sandbox
            test_results = self.sandbox.run(code, problem.get("tests", []))
            self.logger.log_test_result(
                problem_id, generation_id, 0, 
                test_results["passed_tests"], test_results["total_tests"],
                test_results["failed_test_ids"], test_results["timeout_tests"],
                test_results["crash_tests"], test_results["execution_time_ms"], 
                test_results["peak_memory_kb"]
            )
            
            # 3. Validate
            validation = await self.validator.validate(code, problem, test_results)
            
            # 4. Evaluate & 5. Aggregate
            fitness = self.fitness_scorer.calculate_fitness(code, test_results, eval_genome)
            
            # 6. Critique
            diagnosis = self.critic.critique(code, test_results, validation, crit_genome)
            
            # 7. Mutate
            new_gen_genome = self.mutator.propose(diagnosis, gen_genome, mut_genome)
            
            # Log generation summary (Placeholder)
            print(f"Problem {problem_id} fitness: {fitness['fitness_value']:.2f} | Validation: {validation['is_correct']}")

        # Co-Score, Select, Breed logic goes here...
        # ...
