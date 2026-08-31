import json
import sys
import os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

files = {
    "Baseline A (Zero-shot)": "structured_reports/31082026_10-18-15.json",
    "Baseline B (Static Reflection)": "structured_reports/31082026_10-28-21.json",
    "Baseline C (Random Mutation)": "structured_reports/31082026_10-31-47.json",
    "Evolved Population": "structured_reports/31082026_10-41-47.json"
}

reports_summary = []

for name, path in files.items():
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    start_dt = datetime.fromisoformat(data["start_time"])
    end_dt = datetime.fromisoformat(data["end_time"])
    duration = (end_dt - start_dt).total_seconds()
    
    mode = data.get("mode")
    pop_size = data.get("pop_size")
    problems = data.get("problems_evaluated", [])
    
    total_candidates = 0
    all_fitness_values = []
    correctness_scores = []
    runtime_scores = []
    memory_scores = []
    complexity_scores = []
    robustness_scores = []
    
    total_passed_tests = 0
    total_test_cases = 0
    total_timeouts = 0
    total_crashes = 0
    
    problem_details = []
    
    for p_idx, p in enumerate(problems):
        pid = p.get("problem_id", f"Problem_{p_idx+1}")
        gens = p.get("generations", [])
        
        p_fits = []
        p_passed_tests = 0
        p_tot_tests = 0
        
        gen_summaries = []
        
        for g in gens:
            gid = g.get("generation_id")
            evals = g.get("evaluations", [])
            sel = g.get("selection_and_breeding")
            
            gen_fits = []
            for ev in evals:
                total_candidates += 1
                fit_obj = ev.get("fitness", {})
                fit_val = fit_obj.get("fitness_value", 0.0)
                gen_fits.append(fit_val)
                all_fitness_values.append(fit_val)
                p_fits.append(fit_val)
                
                bd = fit_obj.get("breakdown", {})
                correctness_scores.append(bd.get("correctness", 0.0))
                runtime_scores.append(bd.get("runtime", 0.0))
                memory_scores.append(bd.get("memory", 0.0))
                complexity_scores.append(bd.get("complexity", 0.0))
                robustness_scores.append(bd.get("robustness", 0.0))
                
                tr = ev.get("test_results", {})
                passed_t = tr.get("passed_tests", 0)
                tot_t = tr.get("total_tests", 0)
                p_passed_tests += passed_t
                p_tot_tests += tot_t
                total_passed_tests += passed_t
                total_test_cases += tot_t
                
                total_timeouts += len(tr.get("timeout_tests", []))
                total_crashes += len(tr.get("crash_tests", []))
                
            gen_summaries.append({
                "gid": gid,
                "evals": len(evals),
                "max_fit": max(gen_fits) if gen_fits else 0,
                "avg_fit": sum(gen_fits)/len(gen_fits) if gen_fits else 0,
                "min_fit": min(gen_fits) if gen_fits else 0,
                "sel": sel
            })
            
        problem_details.append({
            "pid": pid,
            "generations_count": len(gens),
            "max_fit": max(p_fits) if p_fits else 0,
            "avg_fit": sum(p_fits)/len(p_fits) if p_fits else 0,
            "passed_tests": p_passed_tests,
            "tot_tests": p_tot_tests,
            "gen_summaries": gen_summaries
        })
        
    reports_summary.append({
        "name": name,
        "path": path,
        "mode": mode,
        "pop_size": pop_size,
        "duration": duration,
        "num_problems": len(problems),
        "total_candidates": total_candidates,
        "max_fitness": max(all_fitness_values) if all_fitness_values else 0,
        "avg_fitness": sum(all_fitness_values)/len(all_fitness_values) if all_fitness_values else 0,
        "min_fitness": min(all_fitness_values) if all_fitness_values else 0,
        "avg_correctness": sum(correctness_scores)/len(correctness_scores) if correctness_scores else 0,
        "avg_runtime": sum(runtime_scores)/len(runtime_scores) if runtime_scores else 0,
        "avg_memory": sum(memory_scores)/len(memory_scores) if memory_scores else 0,
        "avg_complexity": sum(complexity_scores)/len(complexity_scores) if complexity_scores else 0,
        "avg_robustness": sum(robustness_scores)/len(robustness_scores) if robustness_scores else 0,
        "passed_tests": total_passed_tests,
        "total_tests": total_test_cases,
        "timeouts": total_timeouts,
        "crashes": total_crashes,
        "problem_details": problem_details
    })

print("=" * 100)
print("EVOCODE STRUCTURED REPORTS DETAILED ANALYSIS")
print("=" * 100)

for r in reports_summary:
    print(f"\n>>> {r['name']} ({r['path']})")
    print(f"    Mode: {r['mode']} | Pop Size: {r['pop_size']} | Duration: {r['duration']:.2f}s ({r['duration']/60:.2f}m)")
    print(f"    Total Evaluated Candidates: {r['total_candidates']} across {r['num_problems']} problems")
    print(f"    Fitness: Max = {r['max_fitness']:.4f} | Avg = {r['avg_fitness']:.4f} | Min = {r['min_fitness']:.4f}")
    print(f"    Breakdown (Avg): Correctness={r['avg_correctness']:.2f}, Memory={r['avg_memory']:.2f}, Complexity={r['avg_complexity']:.2f}, Runtime={r['avg_runtime']:.2f}, Robustness={r['avg_robustness']:.2f}")
    print(f"    Tests Passed: {r['passed_tests']}/{r['total_tests']} | Timeouts: {r['timeouts']} | Crashes: {r['crashes']}")
    for p in r["problem_details"]:
        print(f"      - Problem {p['pid']}: {p['generations_count']} Gens | Max Fit = {p['max_fit']:.4f} | Avg Fit = {p['avg_fit']:.4f}")
        for g in p["gen_summaries"]:
            sel_str = f" | Selection: {g['sel']}" if g['sel'] else ""
            print(f"        Gen {g['gid']}: {g['evals']} cands, MaxFit={g['max_fit']:.4f}, AvgFit={g['avg_fit']:.4f}{sel_str}")

# Save json analysis report for clean formatted display
with open("scratch/analysis_summary.json", "w", encoding="utf-8") as f:
    json.dump(reports_summary, f, indent=2)
