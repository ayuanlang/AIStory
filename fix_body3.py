with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\x8f\xaf\xe7\x94\xa8\xef\xbc\x9a\xe8\xbf\x94\xe5\x9b\x9e\xe5\x86\x85\xe5\xae\xb9\xe7\xbb\x93\xe6\x9e\x84\xe4\xb8\x8d\xe5\xae\x8c\xe6\x95\xb4\xe6\x88\x96\xe6\xa0\xa1\xe9\xaa\x8c\xe6\x9c\xaa\xe9\x80\x9a\xe8\xbf\x87' in line:
        s = '    return "场景分析结果不可用：返回内容结构不完整或校验未通过。请直接重新执行剧本分析。"'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
