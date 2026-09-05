import json

data = json.load(open('data/train_problems.json'))
for idx in [5, 6]:
    p = data[idx]
    pid = p["id"]
    title = p["title"]
    desc = p["description"]
    print(f"Problem {pid} - {title}")
    print(f"  description: {desc}")
    print()
