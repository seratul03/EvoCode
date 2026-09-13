import asyncio
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.client import EvoClient
from run_autonomous import generate_problems

async def main():
    parser = argparse.ArgumentParser(description="Generate a static benchmark suite")
    parser.add_argument("--count", "-c", type=int, default=50, help="Number of problems to generate")
    parser.add_argument("--out", "-o", type=str, default="benchmark_suite.json", help="Output file")
    args = parser.parse_args()

    client = EvoClient()
    
    problems = []
    
    # Load existing problems if they exist to avoid overwriting and append
    if os.path.exists(args.out):
        try:
            with open(args.out, "r", encoding="utf-8") as f:
                problems = json.load(f)
                print(f"Loaded {len(problems)} existing problems from {args.out}")
        except Exception:
            pass

    start_id = max([p.get("id", 0) for p in problems] + [0]) + 1
    
    target_count = args.count
    while len(problems) < target_count:
        needed = target_count - len(problems)
        batch_size = min(needed, 5) # Generate in batches of 5 to avoid long hangs
        
        print(f"\nGenerating batch of {batch_size} problems ({len(problems)}/{target_count} done)...")
        try:
            batch = await generate_problems(client, batch_size, start_id)
            if batch:
                problems.extend(batch)
                start_id += len(batch)
                
                # Save progress incrementally
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump(problems, f, indent=2)
                print(f"Saved progress. Total problems: {len(problems)}")
            else:
                print("Failed to generate any valid problems in this batch. Retrying...")
                await asyncio.sleep(2)
        except Exception as e:
            print(f"Error during generation: {e}")
            await asyncio.sleep(5)
            
    print(f"\nSuccessfully generated and saved {len(problems)} problems to {args.out}.")

if __name__ == "__main__":
    asyncio.run(main())
