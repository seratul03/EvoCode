import json
import os

files = {
    'Baseline A (Zero-shot)': 'structured_reports/31082026_10-18-15.json',
    'Baseline B (Static Reflection)': 'structured_reports/31082026_10-28-21.json',
    'Baseline C (Random Mutation)': 'structured_reports/31082026_10-31-47.json',
    'Evolved Population': 'structured_reports/31082026_10-41-47.json'
}

for label, path in files.items():
    if not os.path.exists(path):
        print(f"File not found: {path}")
        continue
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=" * 60)
    print(f"REPORT: {label}")
    print(f"Path: {path}")
    print(f"Mode: {data.get('mode')}")
    print(f"Population Size: {data.get('pop_size')}")
    print(f"Start Time: {data.get('start_time')}")
    print(f"End Time: {data.get('end_time')}")
    
    problems = data.get('problems_evaluated', [])
    print(f"Number of Problems Evaluated: {len(problems)}")
    
    for p_idx, p in enumerate(problems):
        p_id = p.get('problem_id', p.get('task_id', p.get('id', f'Problem_{p_idx+1}')))
        print(f"\n  --- Problem {p_idx+1}: {p_id} ---")
        
        # Summary metrics on problem level if any
        for k, v in p.items():
            if k not in ['generations', 'prompt_history', 'candidates', 'history', 'problem_data']:
                print(f"    {k}: {v}")
                
        generations = p.get('generations', [])
        print(f"    Total Generations: {len(generations)}")
        
        best_score_overall = 0
        total_candidates = 0
        solved_count = 0
        
        for g_idx, gen in enumerate(generations):
            cands = gen.get('candidates', []) if isinstance(gen, dict) else gen
            total_candidates += len(cands)
            
            gen_best = 0
            cand_summaries = []
            for c in cands:
                score = c.get('score', c.get('fitness', 0))
                passed = c.get('passed', False) or c.get('tests_passed', 0) == c.get('total_tests', -1)
                if score > gen_best:
                    gen_best = score
                if score > best_score_overall:
                    best_score_overall = score
                if passed or score == 1.0:
                    solved_count += 1
                cand_summaries.append(f"s={score}")
                
            print(f"    Gen {g_idx+1}: {len(cands)} cands | best_score={gen_best:.2f} | scores=[{', '.join(cand_summaries[:5])}{'...' if len(cand_summaries)>5 else ''}]")
            
        print(f"    Summary -> Best Score Overall: {best_score_overall:.2f} | Total Solved Solutions: {solved_count}/{total_candidates}")
