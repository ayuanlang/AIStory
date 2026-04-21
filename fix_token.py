with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\x88\x86\xe6\x9e\x90' in line and b'\xe6\x8e\xa8\xe7\x90\x86' in line and b'\xe6\x80\x9d\xe8\xb7\xaf' in line and b'\xe6\x88\x91\xe5\xb0\x86' in line:
        s = '        if any(token in preface for token in ["analysis", "reasoning", "推理", "思路", "我将", "我认为"]):'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
