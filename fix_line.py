with open('backend/app/api/endpoints.py', 'rb') as f:
    lines = f.readlines()
lines[377] = '        "cn_required": ["六视图", "正面", "背面", "侧面", "四分之三", "特写", "细节", "背景", "纯白"],\r\n'.encode('utf-8')
with open('backend/app/api/endpoints.py', 'wb') as f:
    f.writelines(lines)
