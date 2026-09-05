import json

file_path = 'data/train_problems.json'
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for p in data:
    if p["id"] == 6:
        if "For n < 0" not in p["description"]:
            p["description"] += " For n < 0, return n itself. For n == 0, return 0."
    elif p["id"] == 7:
        if "non-bracket characters" not in p["description"]:
            p["description"] += " Note: The string must contain ONLY bracket characters. If it contains any other characters, it is considered invalid and you must return False. An empty string is valid."

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print("Updated descriptions for problem 6 and 7.")
