with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'reasons_cn[:3]' in line:
        lines[i] = '        detail_parts.append("，".join(reasons_cn[:3]))\n'
    elif 'raw_reasons[:3]' in line:
        lines[i] = '        detail_parts.append("技术明细：" + "，".join(raw_reasons[:3]))\n'
    elif 'detail_parts if part' in line:
        lines[i] = '    body = "；".join([part for part in detail_parts if part])\n'
    elif '场景分析结果不可用' in line:
        # replace the bad quote at the end
        lines[i] = '        return "场景分析结果不可用：" + body + "。请直接重新执行剧本分析。"\n'

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
