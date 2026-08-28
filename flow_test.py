import asyncio
import json
from src.evoflow import EvoFlowOrchestrator

async def main():
    print("Loading training problems...")
    with open("data/train_problems.json", "r") as f:
        problems = json.load(f)
        
    # We will test on a subset to keep the dry run manageable
    # Let's use the first 2 problems for the dry run to avoid excessive API usage
    test_subset = problems[:2]
    
    print(f"Starting EvoFlow on {len(test_subset)} problems.")
    
    # Initialize the orchestrator with population size of 5
    orchestrator = EvoFlowOrchestrator(pop_size=5)
    
    # Run for 2 generations
    await orchestrator.run_generations(num_generations=2, problems=test_subset)
    
    print("Run completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
