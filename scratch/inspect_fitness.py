import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("structured_reports/31082026_10-18-15.json", "r", encoding="utf-8") as f:
    data = json.load(f)

p0 = data["problems_evaluated"][0]
ev0 = p0["generations"][0]["evaluations"][0]

print("Fitness type:", type(ev0.get("fitness")))
print("Fitness value:", ev0.get("fitness"))
print("Validation value:", ev0.get("validation"))
print("Critic diagnosis value:", ev0.get("critic_diagnosis"))
