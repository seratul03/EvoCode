import json
data = json.load(open('data/train_problems.json'))
for idx in [5, 6]:
    p = data[idx]
    print(f"Problem {p['id']} - {p['title']}")
    print(f"  function_signature: {p['function_signature']}")
    print(f"  Tests:")
    for t in p['tests']:
        print(f"    id={t['id']} input={t['input']} expected={t['expected']}")
    print()
