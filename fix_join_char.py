with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe3\x80\x81.join([str(item)' in line:
        s = '        joined = "、".join([str(item).strip() for item in missing if str(item).strip()])'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
