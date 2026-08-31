import json

path = 'structured_reports/31082026_10-41-47.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Top keys:", list(data.keys()))
probs = data.get('problems_evaluated', [])
print("Number of problems:", len(probs))
if probs:
    p0 = probs[0]
    print("Problem 0 keys:", list(p0.keys()))
    gens = p0.get('generations', [])
    print("Number of generations in problem 0:", len(gens))
    if gens:
        g0 = gens[0]
        print("Gen 0 type:", type(g0))
        if isinstance(g0, dict):
            print("Gen 0 keys:", list(g0.keys()))
            print("Gen 0 content sample:", str(g0)[:300])
        elif isinstance(g0, list):
            print("Gen 0 list len:", len(g0))
            if g0:
                print("Elem 0 type:", type(g0[0]))
                print("Elem 0:", str(g0[0])[:300])
