import sys
import traceback
import re
sys.path.append('c:/AS/AIStory/backend')
from app.api.endpoints import parse_shots_markdown_table, sanitize_llm_markdown_output

md_text = '''
| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | Keyframes (CN) | End Frame (CN) | Associated Entities |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01_SC01_SH01 | 鸟瞰 | SC01 | P1 | [Global Style] A | B | 9 | NO | C | D | E | NO | F | G |
| EP01_SC01_SH02 | 鸟瞰 | SC01 | P1 | [Global Style] A | B | 8 | NO | C | D | E | NO | F | G |
| EP01_SC01_SH03 | 鸟瞰 | SC01 | P1 | [Global Style] A | B | 8 | NO | C | D | E | NO | F | G |
| EP01_SC01_SH04 | 鸟瞰 | SC01 | P1 | [Global Style] A | B | 5 | NO | C | D | E | NO | F | G |
| EP01_SC01_SH05 | 鸟瞰 | SC01 | P1 | [Global Style] A | B | 7 | NO | C | D | E | NO | F | G |
| EP01_SC01_SH06 | 鸟瞰 | SC01 | P1 | [Global Style] A | B | 8 | NO | C | D | E | NO | F | G |
'''

response_content = sanitize_llm_markdown_output(md_text)

cleaned_lines = []
for line in str(response_content or "").splitlines():
    stripped = line.strip()
    if stripped and not stripped.startswith("|"): # Simplified regex check
        continue
    cleaned_lines.append(line)
response_content = "\n".join(cleaned_lines).strip()

headers, shots_data, table_line_count = parse_shots_markdown_table(response_content)
print(f"Parsed rows count: {len(shots_data)}")
print(f"Table line count: {table_line_count}")

if table_line_count >= 4 and len(shots_data) > 0 and (len(shots_data) * 2) <= table_line_count:
    print(f"FAILED safety check! (shots_data: {len(shots_data)}, table_line_count: {table_line_count})")
else:
    print("PASSED safety check!")
