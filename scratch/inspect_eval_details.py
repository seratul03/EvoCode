import json
import sys

# Force UTF-8 output stdout
sys.stdout.reconfigure(encoding='utf-8')

files = {
    "Baseline A (Zero-shot)": "structured_reports/31082026_10-18-15.json",
    "Baseline B (Static Reflection)": "structured_reports/31082026_10-28-21.json",
    "Baseline C (Random Mutation)": "structured_reports/31082026_10-31-47.json",
    "Evolved Population": "structured_reports/31082026_10-41-47.json"
}

for name, path in files.items():
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("=" * 80)
    print(f"REPORT: {name} ({path})")
    
    problems = data.get("problems_evaluated", [])
    for p_idx, p in enumerate(problems):
        pid = p.get("problem_id", f"Problem_{p_idx+1}")
        gens = p.get("generations", [])
        print(f"\n  Problem: {pid} (Generations: {len(gens)})")
        
        all_fitnesses = []
        all_passed = 0
        total_evals = 0
        
        for g in gens:
            gid = g.get("generation_id")
            evals = g.get("evaluations", [])
            total_evals += len(evals)
            gen_fits = []
            for ev in evals:
                fit = ev.get("fitness", 0.0)
                gen_fits.append(fit)
                all_fitnesses.append(fit)
                tr = ev.get("test_results", {})
                passed_tests = tr.get("passed_tests", 0)
                tot_tests = tr.get("total_tests", 0)
                if passed_tests > 0 and passed_tests == tot_tests:
                    all_passed += 1
            print(f"    Gen {gid}: Evals={len(evals)} | Fitnesses={[round(x, 4) for x in gen_fits]}")
            
        print(f"  Summary for Problem {pid}: Total Evals={total_evals}, Solved={all_passed}, Max Fitness={max(all_fitnesses) if all_fitnesses else 0:.4f}, Avg Fitness={sum(all_fitnesses)/len(all_fitnesses) if all_fitnesses else 0:.4f}")
