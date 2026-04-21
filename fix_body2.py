with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\x8f\xaf\xe7\x94\xa8\xef\xbc\x9a' in line and b'body' in line and b'\xe5\x88\x86\xe6\x9e\x90' in line:
        s = '    return "场景分析结果不可用：" + body + "。请直接重新执行剧本分析。"'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
