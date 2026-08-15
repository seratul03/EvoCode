import os
import json
import random
from collections import defaultdict
from datasets import load_dataset

def generate_subset():
    print("Loading SWE-bench Lite dataset...")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    # Group instances by repository to ensure diversity
    repo_groups = defaultdict(list)
    for instance in dataset:
        repo_groups[instance["repo"]].append(instance["instance_id"])
    
    subset = []
    target_size = 25
    
    # Pick one problem from each repo in a round-robin fashion until we hit 25
    repos = list(repo_groups.keys())
    random.seed(42) # For reproducibility
    
    while len(subset) < target_size and repos:
        for repo in list(repos):
            if len(subset) >= target_size:
                break
            if repo_groups[repo]:
                # Pop a random instance from this repo
                idx = random.randint(0, len(repo_groups[repo]) - 1)
                subset.append(repo_groups[repo].pop(idx))
            else:
                repos.remove(repo) # No more instances in this repo
                
    # Save the subset to a JSON file
    os.makedirs("experiments", exist_ok=True)
    output_path = "experiments/subset.json"
    
    with open(output_path, "w") as f:
        json.dump(subset, f, indent=4)
        
    print(f"\nSuccessfully selected {len(subset)} diverse instances across multiple repositories.")
    print(f"Saved subset list to: {output_path}")
    print("\nHere are the selected instances:")
    for i, inst in enumerate(subset, 1):
        print(f"{i}. {inst}")

if __name__ == "__main__":
    generate_subset()