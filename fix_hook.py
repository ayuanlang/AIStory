with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\xbc\x80\xe5\x9c\xba\xe9\x92\xa9\xe5\xad\x90' in line and b'hook' in line:
        s = '        if (not hook) and ("开场钩子" in s):'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
