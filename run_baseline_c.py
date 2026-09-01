import asyncio
import json
from src.evoflow import EvoFlowOrchestrator

async def main():
    print("Loading training problems...")
    with open("data/train_problems.json", "r", encoding="utf-8") as f:
        problems = json.load(f)
        
    print(f"Starting EvoFlow on first 10 training problems.")
    
    # Baseline C: Random mutation, 5 agents per generation, 6 generations
    orchestrator = EvoFlowOrchestrator(pop_size=5)
    await orchestrator.run_generations(num_generations=6, problems=problems[:10], mode="baseline_c")
    print("Run completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
