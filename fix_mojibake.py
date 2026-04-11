import sys
import re

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "渚涘簲鍟嗚皟鐢ㄥけ璐" in line:
        if "if" in line:
            new_lines.append(line.split('if')[0] + 'if "供应商调用失败" in detail:\n')
        elif "return" in line:
            new_lines.append(line.split('return')[0] + 'return f"{vendor} 供应商调用失败: {detail}"\n')
        else:
            new_lines.append(line)
    elif "reasons_cn.append(" in line:
        if "ANALYSIS_STRUCTURE_INCOMPLETE" in "".join(new_lines[-2:]):
            new_lines.append(line.split('reasons_cn.append(')[0] + 'reasons_cn.append("结果缺少必要结构字段")\n')
        elif "ANALYSIS_SUBJECTS_UNVERIFIED" in "".join(new_lines[-2:]):
            new_lines.append(line.split('reasons_cn.append(')[0] + 'reasons_cn.append("部分/全部主体未能验证")\n')
        elif "ANALYSIS_SUBJECTS_INCOMPLETE" in "".join(new_lines[-2:]):
            new_lines.append(line.split('reasons_cn.append(')[0] + 'reasons_cn.append("部分/全部主体缺少基本描述")\n')
        elif "ANALYSIS_OUTPUT_TRUNCATED" in "".join(new_lines[-2:]):
            new_lines.append(line.split('reasons_cn.append(')[0] + 'reasons_cn.append("大模型输出被截断")\n')
        elif "ANALYSIS_JSON_INVALID" in "".join(new_lines[-2:]):
            new_lines.append(line.split('reasons_cn.append(')[0] + 'reasons_cn.append("大模型输出无法解析为JSON")\n')
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Done!')
