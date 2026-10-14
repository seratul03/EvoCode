import asyncio
import json
from src.evoflow import EvoFlowOrchestrator

async def main():
    print("Loading training problems...")
    with open("data/train_problems.json", "r", encoding="utf-8") as f:
        problems = json.load(f)
        
    problems = [p for p in problems if p["id"] in [6, 7]]
        
    print(f"Starting EvoFlow on problem 6 and 7.")
    
    orchestrator = EvoFlowOrchestrator(pop_size=1)
    await orchestrator.run_generations(num_generations=2, problems=problems, mode="baseline_a")
    print("Run completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
