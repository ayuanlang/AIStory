with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

text = re.sub(
    r'camera_fixed = _pick_tool_value\("cameraFixed"\)\n\s*payload\["cameraFixed"\] = _normalize_bool\(camera_fixed, False\)',
    'camera_fixed = _pick_tool_value("cameraFixed")\n            payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false" if "seedance" in str(video_model).lower() else _normalize_bool(camera_fixed, False)',
    text
)

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
