import os
import subprocess
import json
import glob
from statistics import mean

# Define the research conditions
CONDITIONS = [
    {
        "name": "1_single_agent_no_evolution",
        "flags": ["--single-agent", "--disable-evolution", "--disable-memory"]
    },
    {
        "name": "2_multi_agent_no_evolution",
        "flags": ["--disable-evolution", "--disable-memory"]
    },
    {
        "name": "3_evocode_no_memory",
        "flags": ["--disable-memory", "--disable-collaboration"]
    },
    {
        "name": "4_evocode_no_collaboration",
        "flags": ["--disable-collaboration"]
    },
    {
        "name": "5_evocode_full",
        "flags": []
    }
]

def run_condition(condition, runs=1, gens=2):
    print(f"\n{'='*60}")
    print(f"Running Condition: {condition['name']}")
    print(f"Flags: {' '.join(condition['flags'])}")
    print(f"{'='*60}")
    
    # Run the autonomous pipeline with the specific flags
    cmd = ["python", "run_autonomous.py", "--runs", str(runs), "--gens", str(gens)] + condition["flags"]
    subprocess.run(cmd, check=True)

def aggregate_reports():
    reports_dir = "structured_reports"
    if not os.path.exists(reports_dir):
        return []
        
    all_reports = []
    for filepath in glob.glob(f"{reports_dir}/*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                report = json.load(f)
                all_reports.append(report)
        except Exception:
            pass
            
    return all_reports

def compute_metrics(reports):
    """
    Computes simple placeholder metrics from the raw reports.
    In a real research scenario, we would tag reports with the condition name.
    For this script, we just aggregate whatever is in the structured_reports folder.
    """
    total_problems = 0
    solved_problems = 0
    total_evolutions = 0
    total_generations = 0
    
    for r in reports:
        for p in r.get("problems_evaluated", []):
            total_problems += 1
            if p.get("evolution_trigger"):
                total_evolutions += 1
                
            # Check if solved
            is_solved = False
            for gen in p.get("generations", []):
                total_generations += 1
                for evaluation in gen.get("evaluations", []):
                    test_results = evaluation.get("test_results", {})
                    if test_results.get("passed_tests", 0) == test_results.get("total_tests", -1) and test_results.get("total_tests", 0) > 0:
                        is_solved = True
                        break
            if is_solved:
                solved_problems += 1
                
    success_rate = (solved_problems / max(1, total_problems)) * 100
    
    print("\n--- AGGREGATE METRICS ---")
    print(f"Total Runs Analyzed: {len(reports)}")
    print(f"Total Problems: {total_problems}")
    print(f"Solved Problems: {solved_problems} ({success_rate:.1f}%)")
    print(f"Total Evolution Triggers: {total_evolutions}")
    print(f"Average Generations per Problem: {total_generations / max(1, total_problems):.2f}")
    print("-------------------------")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EvoCode Final Research Evaluation Harness")
    parser.add_argument("--dry-run", action="store_true", help="Run a fast, 1-problem 1-generation test to verify the harness.")
    parser.add_argument("--aggregate-only", action="store_true", help="Do not run experiments, just aggregate existing reports.")
    args = parser.parse_args()
    
    if not args.aggregate_only:
        # Clear old reports before running
        import shutil
        if os.path.exists("structured_reports"):
            shutil.rmtree("structured_reports")
        os.makedirs("structured_reports", exist_ok=True)
        
        runs = 1 if args.dry_run else 10
        gens = 1 if args.dry_run else 3
        
        for condition in CONDITIONS:
            try:
                run_condition(condition, runs=runs, gens=gens)
            except subprocess.CalledProcessError as e:
                print(f"Error running condition {condition['name']}: {e}")
                
    # Parse the outputs
    reports = aggregate_reports()
    compute_metrics(reports)
