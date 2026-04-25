# -*- coding: utf-8 -*-
import sys

file_path = 'C:\\AS\\AIStory\\backend\\app\\services\\llm_service.py'
with open(file_path, 'rb') as f:
    data = f.read()

text = data.decode('utf-8', errors='replace')

import re
old_regex = r'def _vendor_failed_message.*?return f"\{vendor\}.*? \{detail\}"'
new_func = '''def _vendor_failed_message(self, provider: Any, reason: Any) -> str:
        vendor = self._vendor_label(provider)
        detail = str(reason or "unknown error").strip()
        if "供应商调用失败" in detail:
            return detail
        return f"{vendor}供应商调用失败: {detail}"'''

new_text = re.sub(old_regex, new_func, text, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_text)

print("done")
