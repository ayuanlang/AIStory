import sys
sys.path.append('c:/AS/AIStory/backend')
from app.api.endpoints import parse_shots_markdown_table, _validate_shot_rows_for_apply_with_tolerance

md_text = """| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | Keyframes (CN) | End Frame (CN) | Associated Entities |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01_SC01_SH01 | 鸟瞰引入与俯冲揭示 | EP01_SC01 | P1 空间建立(5s)+P2 俯冲揭示(4s)=9s。通过航拍跟随与俯冲建立世界观与悬疑，作为开场长镜头。 | [Global Style] cinematic realism, high contrast, historical weight,<br>[Context & Lighting] vast land under dim yellow sky, distant city fading into haze,<br>[Camera & Composition] Aerial Wide Shot, high angle, 24mm lens, deep depth of field,<br>[Staging & Spatial] ENV:[Xianyang City Aerial] in far background, PROP:[Black Imperial Carriage] exiting north gate at midground,<br>[Subject Action (Static)] a red-beaked crow gliding mid-air,<br>[Layers & Details] farmland textures below. | [Global Style] cinematic realism, high contrast,<br>[Camera Movement] Tracking forward following the crow, then transitioning into a rapid descending dive (dolly down + tilt down) from aerial to vertical plunge.<br>[Action Beat Chain] (P1) The crow glides steadily forward over the moving PROP:[Black Imperial Carriage], crossing fields -> resulting in spatial continuity. (P2) The crow suddenly spirals downward rapidly, syncing with rising wind SFX -> revealing ENV:[Kengru Valley] and the massive pit filled with bodies.<br>[Dynamic Atmosphere] lighting darkens gradually, shadows deepen as descent intensifies. | 9 | NO | [Global Style] cinematic realism,<br>[Context & Lighting] oppressive dim light over a massive pit,<br>[Camera & Composition] High Angle Wide Shot, 24mm lens,<br>[Staging & Spatial] ENV:[Kengru Valley] dominates frame, pit center,<br>[Subject Action (Static)] bodies densely packed below,<br>[Layers & Details] dust and faint movement. | 写实主义电影质感，高对比；昏黄天色下广阔大地，远处城池渐隐；航拍广角，24mm大景深；远景为ENV:[Xianyang City Aerial]，中景为驶出的PROP:[Black Imperial Carriage]；一只红嘴山鸦悬空滑翔；下方农田纹理清晰。 | 镜头跟随山鸦平稳前行，掠过缓慢移动的车驾与农田，保持空间连续。随后山鸦骤然收翼俯冲，镜头同步快速下压并向下倾斜，风声骤起，与俯冲节奏同步，最终揭示ENV:[Kengru Valley]巨大深坑与堆积尸体。光线逐渐压暗，阴影加重。 | NO | 写实主义风格；压抑昏暗光线笼罩深坑；高角度广角镜头；ENV:[Kengru Valley]占据画面中心；坑底尸体密集；尘土与细微动势可见。 | ENV:[Kengru Valley], PROP:[Black Imperial Carriage] |
"""
headers, rows, line_count = parse_shots_markdown_table(md_text)
try:
    print(_validate_shot_rows_for_apply_with_tolerance(rows, source_label="test"))
    print("VALIDATION SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
