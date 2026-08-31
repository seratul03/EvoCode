import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('data/train_problems.json') as f:
    probs = json.load(f)
for i in range(17, 30):
    p = probs[i]
    sig = p['function_signature'][:100]
    title = p['title']
    print(f'[{i}] {title}')
    print(f'     sig: {sig}')
    print()
