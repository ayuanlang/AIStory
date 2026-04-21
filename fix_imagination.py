with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\xa2\x9e\xe5\x8a\xa0\xe6\x83\xb3\xe8\xb1\xa1\xe5\x8a\x9b' in line and b'increase imagination' in line:
        s = '    if "增加想象力" in raw or "increase imagination" in normalized:'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
