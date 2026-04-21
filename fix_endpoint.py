import re

path = 'backend/app/api/endpoints.py'
text = open(path, 'r', encoding='utf-8').read()

text = re.sub(
    r'(task_type="signup_bonus",\s*provider="system",\s*model="email_verification",\s*)details=(\{)',
    r'description="signup_bonus", \n            details={\n                "task_type": "signup_bonus", "provider": "system", "model": "email_verification",',
    text
)


text = re.sub(
    r'(task_type="recharge",\s*provider="wechat",\s*model="cny",\s*)details=(\{)',
    r'description="recharge", \n                        details={\n                            "task_type": "recharge", "provider": "wechat", "model": "cny",',
    text
)

open(path, 'w', encoding='utf-8').write(text)
print("Done")
