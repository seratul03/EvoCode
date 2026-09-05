import json
import asyncio
from src.agents.generator import GeneratorAgent
from src.sandbox import Sandbox
from src.genome import GeneratorGenome

class CanaryPipeline:
    """
    Staging gate for mutations.
    Before a mutation is promoted to the population, it must solve a small suite of baseline problems.
    If it fails (due to syntax errors or logic bugs introduced by a bad prompt rewrite), it is rejected.
    """
    def __init__(self, client):
        self.client = client
        self.sandbox = Sandbox(timeout_seconds=5)
        
        # Load baseline problems
        with open("data/train_problems.json", "r", encoding="utf-8") as f:
            all_problems = json.load(f)
            # Pick 2 fast, simple problems for the canary suite (e.g., Two Sum)
            self.canary_suite = all_problems[:2]
            
    async def validate_mutation(self, proposed_genome: GeneratorGenome, language: str = "Python") -> bool:
        """
        Runs the proposed genome against the canary suite.
        Returns True if it passes ALL canary tests, False otherwise.
        """
        print(f"    [Canary] Validating proposed mutation ({proposed_genome.prompt_style}, temp={proposed_genome.temperature:.2f})...")
        
        # Create a temporary agent
        agent = GeneratorAgent(self.client, language=language)
        
        for problem in self.canary_suite:
            try:
                code = await agent.solve(problem, proposed_genome)
                test_results = self.sandbox.run(
                    code, 
                    problem.get("tests", []), 
                    language=language, 
                    template=problem.get("function_signature")
                )
                
                # The mutation must result in code that completely solves the basic problem
                if test_results["passed_tests"] < test_results["total_tests"]:
                    print(f"      [Canary] Failed on '{problem['title']}'. Mutation rejected.")
                    return False
                    
            except Exception as e:
                print(f"      [Canary] Exception during evaluation: {e}. Mutation rejected.")
                return False
                
        print("      [Canary] Mutation passed staging suite. Promoting...")
        return True
