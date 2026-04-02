import re
path = r'C:\AIStory\backend\app\api\endpoints.py'
with open(path, 'r', encoding='utf-8') as f: t = f.read()

t = t.replace(
'''                if t in {"environment", "environments", "env", "场景", "环境"}:
                    return "environment"
                return ""''',
'''                if t in {"environment", "environments", "env", "场景", "环境"}:
                    return "environment"
                if t in {"cover", "covers", "封面", "封面海报"}:
                    return "cover"
                return ""'''
)

t = t.replace(
'''                if normalized_type == "environment":
                    return f"ENV:[{clean_name}]"
                return f"SUBJECT:[{clean_name}]"''',
'''                if normalized_type == "environment":
                    return f"ENV:[{clean_name}]"
                if normalized_type == "cover":
                    return f"COVER:[{clean_name}]"
                return f"SUBJECT:[{clean_name}]"'''
)

with open(path, 'w', encoding='utf-8') as f: f.write(t)
