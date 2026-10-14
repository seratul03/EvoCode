import asyncio
import json
from src.evoflow import EvoFlowOrchestrator

async def main():
    print("Loading training problems...")
    with open("data/train_problems.json", "r") as f:
        problems = json.load(f)
        
    test_subset = problems[:2]
    
    print(f"Starting EvoFlow on {len(test_subset)} problems.")
    
    orchestrator = EvoFlowOrchestrator(pop_size=5)
    
    await orchestrator.run_generations(num_generations=2, problems=test_subset)
    
    print("Run completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
