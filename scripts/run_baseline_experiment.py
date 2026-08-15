import os
import sys
import json
import asyncio
from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.evaluator import Task
from baseline.baseline_pipeline import BaselinePipeline

async def run_experiment():
    print("--- Starting Single-Agent Baseline Experiment ---")
    
    subset_path = "experiments/subset.json"
    if not os.path.exists(subset_path):
        print(f"Error: {subset_path} not found. Please run fetch_data.py first.")
        return
        
    with open(subset_path, "r") as f:
        subset_ids = json.load(f)
        
    print("Loading full SWE-bench Lite dataset to fetch issue descriptions...")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    # Filter dataset to only our subset
    instances = [item for item in dataset if item["instance_id"] in subset_ids]
    
    print(f"Found {len(instances)} instances matching our subset.")
    
    pipeline = BaselinePipeline(max_iterations=3)
    results = {}
    
    os.makedirs("logs", exist_ok=True)
    
    for i, instance in enumerate(instances, 1):
        instance_id = instance["instance_id"]
        print(f"\n[{i}/{len(instances)}] Processing: {instance_id}")
        
        # Create a mock task for simulated evaluation
        task = Task(
            instance_id=instance_id,
            setup_script="MOCK_SWE_BENCH",
            test_command="pytest",
            gold_patch=instance["patch"],
            target_file="unknown"
        )
        
        issue_title = instance_id
        issue_body = instance["problem_statement"]
        
        # In a real evaluation, we would fetch the codebase files. 
        # For the simulated run, we omit this to save API tokens and time.
        repo_context = "Repository context omitted for simulated run. Please generate a plausible patch based on the issue description."
        
        try:
            result = await pipeline.run_task(task, issue_title, issue_body, repo_context)
            results[instance_id] = result
            print(f"Result for {instance_id}: {result['status']} (Iterations: {result.get('iterations')})")
        except Exception as e:
            print(f"Error processing {instance_id}: {e}")
            results[instance_id] = {"status": "ERROR", "error": str(e)}
            
    # Save aggregate results
    results_path = "logs/baseline_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"\n--- Experiment Complete ---")
    print(f"Aggregate results saved to {results_path}")
    print("Check logs/baseline_logs.jsonl for the full execution trace!")

if __name__ == "__main__":
    asyncio.run(run_experiment())
