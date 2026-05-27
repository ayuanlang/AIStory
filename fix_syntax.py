with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '供应商调用失' in line:
        if 'if ' in line:
            lines[i] = '    if "供应商调用失败" in detail:\n'
        elif 'return f' in line:
            lines[i] = '    return f"{vendor}供应商调用失败: {detail}"\n'

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
