import re
lines = open('backend/app/api/endpoints.py', 'r', encoding='utf-8').read().splitlines()
for i, l in enumerate(lines):
    if 'task_type=' in l and 'recharge' in l:
        for idx in range(max(0, i-5), min(len(lines), i+6)):
            print(idx, repr(lines[idx]))
        print('---')