with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '结果缺少必要结构段' in line:
        lines[i] = '        reasons_cn.append("结果缺少必要结构段，无法形成完整的场景分析")\n'
    elif '返回内容疑似被截断' in line:
        lines[i] = '        reasons_cn.append("返回内容疑似被截断，结果不完整")\n'

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
