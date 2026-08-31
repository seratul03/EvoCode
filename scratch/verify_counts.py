import json, sys
sys.stdout.reconfigure(encoding='utf-8')
train = json.load(open('data/train_problems.json'))
test  = json.load(open('data/test_problems.json'))
print('Train problems test counts:')
for p in train:
    title = p['title']
    count = len(p['tests'])
    pid = p['id']
    print(f'  [{pid:>2}] {title:<40} {count} tests')
print()
print('Test problems test counts:')
for p in test:
    title = p['title']
    count = len(p['tests'])
    pid = p['id']
    print(f'  [{pid:>2}] {title:<40} {count} tests')
print()
total_train = sum(len(p['tests']) for p in train)
total_test  = sum(len(p['tests']) for p in test)
print(f'Total: {total_train} train tests, {total_test} held-out tests')
