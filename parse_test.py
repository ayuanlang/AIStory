import sys
sys.path.append('c:/AS/AIStory/backend')
from app.api.endpoints import parse_shots_markdown_table, _validate_shot_rows_roundtrip_or_raise, _parse_shot_markdown_or_raise

md_text = """
| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | Keyframes (CN) | End Frame (CN) | Associated Entities |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01_SC01_SH01 | 鸟瞰引入与俯冲揭示 | EP01_SC01 | P1 空间建立(5s)+P2 俯冲揭示(4s)=9s。 | [Global Style] cinematic realism... | [Global Style] cinematic realism,<br>[Camera Movement]... | 9 | NO | [Global Style] cinematic realism... | 写实主义电影质感... | 镜头跟随山鸦平稳前行... | NO | 写实主义风格... | ENV:[Kengru Valley]... |
"""
headers, rows, line_count = parse_shots_markdown_table(md_text)
print("HEADERS:", headers)
print("ROWS: ", len(rows))
try:
    print(_validate_shot_rows_roundtrip_or_raise(rows, source_label="test"))
    print("VALIDATION SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
