import json, sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,'.')
from src.test_augmentor import TestAugmentor

with open('data/train_problems.json', 'r', encoding='utf-8') as f:
    probs = json.load(f)

aug = TestAugmentor()
for i, p in enumerate(probs):
    t0 = time.time()
    result = aug.augment_problem(p, target_count=20)
    elapsed = time.time() - t0
    before = len(p['tests'])
    after = len(result['tests'])
    title = p['title']
    print(f'[{i:>2}] {title:<40}  {before} -> {after}  ({elapsed:.1f}s)', flush=True)
print('Done train_problems')
