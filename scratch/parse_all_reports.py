import json
import os
from datetime import datetime

files = {
    "Baseline A (Zero-shot)": "structured_reports/31082026_10-18-15.json",
    "Baseline B (Static Reflection)": "structured_reports/31082026_10-28-21.json",
    "Baseline C (Random Mutation)": "structured_reports/31082026_10-31-47.json",
    "Evolved Population": "structured_reports/31082026_10-41-47.json"
}

summary_table = []

for name, path in files.items():
    if not os.path.exists(path):
        print(f"Missing {path}")
        continue
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    start_dt = datetime.fromisoformat(data["start_time"])
    end_dt = datetime.fromisoformat(data["end_time"])
    duration_sec = (end_dt - start_dt).total_seconds()
    
    mode = data.get("mode")
    pop_size = data.get("pop_size")
    problems = data.get("problems_evaluated", [])
    
    print("=" * 80)
    print(f"=== {name} ===")
    print(f"File: {path}")
    print(f"Mode: {mode} | Pop Size: {pop_size} | Duration: {duration_sec:.1f}s ({duration_sec/60:.2f} mins)")
    print(f"Start: {data['start_time']} | End: {data['end_time']}")
    print("-" * 80)
    
    total_evals_across_problems = 0
    passed_evals_across_problems = 0
    problem_summaries = []
    
    for p_idx, p in enumerate(problems):
        pid = p.get("problem_id", f"Problem_{p_idx+1}")
        gens = p.get("generations", [])
        
        p_total_evals = 0
        p_passed_evals = 0
        p_scores = []
        
        print(f"\n  Problem ID: {pid} | Generations: {len(gens)}")
        for g in gens:
            gid = g.get("generation_id")
            evals = g.get("evaluations", [])
            sel = g.get("selection_and_breeding", {})
            
            p_total_evals += len(evals)
            
            gen_scores = []
            gen_passed = 0
            for ev in evals:
                # check fields in ev
                ev_keys = list(ev.keys())
                # find pass / score
                score = ev.get("score")
                passed = ev.get("passed")
                test_results = ev.get("test_results") or ev.get("results")
                
                # Check snapshot details
                snap = ev.get("gen_genome_snapshot", {})
                p_style = snap.get("prompt_style")
                temp = snap.get("temperature")
                
                if score is not None:
                    gen_scores.append(score)
                    p_scores.append(score)
                if passed:
                    gen_passed += 1
                    p_passed_evals += 1
                    
            avg_score = sum(gen_scores)/len(gen_scores) if gen_scores else 0
            max_score = max(gen_scores) if gen_scores else 0
            print(f"    Gen {gid}: Evals={len(evals)}, Passed={gen_passed}/{len(evals)}, Max Score={max_score:.2f}, Avg Score={avg_score:.2f}")
            if sel:
                print(f"      Selection/Breeding: {sel}")
                
        total_evals_across_problems += p_total_evals
        passed_evals_across_problems += p_passed_evals
        
        p_max_score = max(p_scores) if p_scores else 0
        p_avg_score = sum(p_scores)/len(p_scores) if p_scores else 0
        problem_summaries.append({
            "pid": pid,
            "total_evals": p_total_evals,
            "passed_evals": p_passed_evals,
            "max_score": p_max_score,
            "avg_score": p_avg_score
        })
        
    summary_table.append({
        "name": name,
        "mode": mode,
        "pop_size": pop_size,
        "duration_sec": duration_sec,
        "total_evals": total_evals_across_problems,
        "passed_evals": passed_evals_across_problems,
        "pass_rate": (passed_evals_across_problems / total_evals_across_problems * 100) if total_evals_across_problems > 0 else 0,
        "problems": problem_summaries
    })

print("\n\n" + "=" * 80)
print("COMPREHENSIVE SUMMARY TABLE")
print("=" * 80)
print(f"{'Run Name':<32} | {'Mode':<12} | {'Pop':<4} | {'Time(s)':<8} | {'Evals':<6} | {'Passed':<6} | {'Pass Rate':<9}")
print("-" * 88)
for s in summary_table:
    print(f"{s['name']:<32} | {s['mode']:<12} | {s['pop_size']:<4} | {s['duration_sec']:<8.1f} | {s['total_evals']:<6} | {s['passed_evals']:<6} | {s['pass_rate']:<8.1f}%")
