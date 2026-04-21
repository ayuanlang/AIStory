with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\x9c\xba\xe6\x99\xaf\xe4\xb8\x8e\xe9\x81\x93\xe5\x85\xb7\xe7\xba\xa6\xe6\x9d\x9f' in line and b'scene_and_props' in line:
        s = '        "场景与道具约束": "scene_and_props",'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)
    if b'\xe6\x95\xb0\xe9\x87\x8f\xe4\xb8\x8e\xe5\x88\xb6\xe4\xbd\x9c\xe5\x8f\xaf\xe8\xa1\x8c\xe6\x80\xa7' in line and b'production_scope' in line:
        s = '        "数量与制作可行性": "production_scope",'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
