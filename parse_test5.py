import sys
sys.path.append('c:/AS/AIStory/backend')
from app.api.endpoints import parse_shots_markdown_table

md_text = """| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | Keyframes (CN) | End Frame (CN) | Associated Entities |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01_SC01_SH01 | 鸟瞰... | EP01_SC01 | P1... | [Global... | [Global... | 9 | NO | [Global... | 写实... | 镜头... | NO | 写实... | ENV... |
| EP01_SC01_SH02 | 鸟瞰... | EP01_SC01 | P1... | [Global... | [Global... | 9 | NO | [Global... | 写实... | 镜头... | NO | 写实... | ENV... |
| EP01_SC01_SH03 | 鸟瞰... | EP01_SC01 | P1... | [Global... | [Global... | 9 | NO | [Global... | 写实... | 镜头... | NO | 写实... | ENV... |
| EP01_SC01_SH04 | 鸟瞰... | EP01_SC01 | P1... | [Global... | [Global... | 9 | NO | [Global... | 写实... | 镜头... | NO | 写实... | ENV... |
| EP01_SC01_SH05 | 鸟瞰... | EP01_SC01 | P1... | [Global... | [Global... | 9 | NO | [Global... | 写实... | 镜头... | NO | 写实... | ENV... |
| EP01_SC01_SH06 | 鸟瞰... | EP01_SC01 | P1... | [Global... | [Global... | 9 | NO | [Global... | 写实... | 镜头... | NO | 写实... | ENV... |
"""
headers, rows, line_count = parse_shots_markdown_table(md_text)
print("Rows:", len(rows), "Line count:", line_count)
