import json
import os
from datasets import load_dataset

def fetch_swe_bench_lite(num_instances: int = 20, output_dir: str = "data"):
    """
    Fetches a subset of SWE-bench Lite and saves them as local JSON files.
    """
    print(f"Fetching {num_instances} instances from princeton-nlp/SWE-bench_Lite...")
    # SWE-bench Lite has splits 'train', 'dev', 'test'.
    # We will pull from 'test' as it is the standard evaluation set.
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Take the first num_instances
    subset = dataset.select(range(num_instances))
    
    saved_count = 0
    for idx, instance in enumerate(subset):
        instance_id = instance['instance_id']
        file_path = os.path.join(output_dir, f"{instance_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(instance, f, indent=2)
        saved_count += 1
        print(f"Saved {instance_id}")
        
    print(f"Successfully saved {saved_count} instances to {output_dir}/")

if __name__ == "__main__":
    fetch_swe_bench_lite(num_instances=20)
