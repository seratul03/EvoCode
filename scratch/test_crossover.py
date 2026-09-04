import asyncio
import os
import sys

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.evoflow import EvoFlowOrchestrator

async def run_test():
    # A simple dummy problem to test with
    problem = {
        "id": 999,
        "description": "Write a function that takes two integers a and b and returns their sum.",
        "tests": [
            {"id": 1, "input": "3, 5", "expected": "8"},
            {"id": 2, "input": "-2, 10", "expected": "8"}
        ]
    }
    
    print("Initializing EvoFlowOrchestrator for Crossover Test...")
    flow = EvoFlowOrchestrator(pop_size=3)
    
    print("Running 2 generations to observe crossover mechanics (breeding phase of Gen 0 -> Gen 1)...")
    await flow.run_generations(num_generations=2, problems=[problem], mode="evolve", disable_circuit_breaker=True)
    
if __name__ == "__main__":
    asyncio.run(run_test())
