with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\xba\x93\xe8\xbf\x9e\xe6\x8e\xa5\xe7\xb9\x81\xe5\xbf\x99' in line and b'\xe8\xaf\xaf' not in line:
        s = '            detail="数据库连接繁忙，请稍后重试",'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
