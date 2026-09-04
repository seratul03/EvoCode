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
    
    problem_report = {"problem_id": problem["id"], "generations": []}
    
    print("Initializing EvoFlowOrchestrator...")
    flow = EvoFlowOrchestrator(pop_size=3)
    
    print("Evaluating Population for generation 0...")
    await flow.evaluate_population(generation_id=0, problem=problem, problem_report=problem_report)
    
    print("\n--- Test Results ---")
    
    generations = problem_report.get("generations", [])
    evaluations = generations[0].get("evaluations", []) if generations else []
    for eval_item in evaluations:
        agent_idx = eval_item["genome_index"]
        agent_name = flow.agent_names[agent_idx]
        generator = flow.generators[agent_idx]
        fitness = eval_item["fitness"]["fitness_value"]
        
        print(f"Agent {agent_name} ({generator.language}): Fitness = {fitness:.4f}")
        print(f"Code Preview:\n{eval_item['generated_code'][:200]}\n...\n")
        print("Test Outputs (Errors):")
        import json
        print(json.dumps(eval_item.get("test_results", {}).get("test_outputs", []), indent=2))
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(run_test())
