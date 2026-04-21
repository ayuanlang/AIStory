with open('backend/app/api/endpoints.py', 'rb') as f:
    text = f.read()

lines = text.splitlines()
for i, line in enumerate(lines):
    if b'\xe5\x8f\x99\xe4\xba\x8b\xe5\x8f\xa3\xe5\x90\xbb\xe4\xb8\x8e\xe8\x8a\x82\xe5\xa5\x8f: "narration_pacing"' in line:
        s = '        "叙事口吻与节奏": "narration_pacing",'
        lines[i] = s.encode('utf-8')
        print('rewrote line', i)

text = b'\n'.join(lines)
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.write(text)
