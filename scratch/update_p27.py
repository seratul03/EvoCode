import json

with open("data/train_problems.json", "r") as f:
    problems = json.load(f)

for p in problems:
    if p["id"] == 27:
        # Check if the reference solution handles divisor == 0
        ref_sol = p["reference_solution"]
        if "if divisor == 0: return 0" not in ref_sol:
            # Add it at the beginning
            p["reference_solution"] = ref_sol.replace("INT_MAX, INT_MIN", "if divisor == 0: return None\n    INT_MAX, INT_MIN")
            print("Updated reference solution for problem 27")

with open("data/train_problems.json", "w") as f:
    json.dump(problems, f, indent=2)
