with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Revert cameraFixed to always use boolean
text = re.sub(
    r'            camera_fixed = _pick_tool_value\("cameraFixed"\)\n            if "seedance" in endpoint_lower or "seedance" in model_lower:\n                payload\["cameraFixed"\] = "true" if _normalize_bool\(camera_fixed, False\) else "false"\n            elif camera_fixed is not None:\n                payload\["cameraFixed"\] = _normalize_bool\(camera_fixed, False\)',
    '            camera_fixed = _pick_tool_value("cameraFixed")\n            payload["cameraFixed"] = _normalize_bool(camera_fixed, False)',
    text
)

# Revert retry logic for cameraFixed to assign false instead of "false"
text = re.sub(
    r'                                        if field_name in \["generateAudio", "cameraFixed"\] and \("seedance" in str\(submit_url\)\.lower\(\) or "seedance" in str\(payload\.get\("model", ""\)\)\.lower\(\)\):\n                                            payload\[field_name\] = "false"',
    r'                                        if field_name == "generateAudio" and ("seedance" in str(submit_url).lower() or "seedance" in str(payload.get("model", "")).lower()):\n                                            payload[field_name] = "false"\n                                        elif field_name == "cameraFixed":\n                                            payload[field_name] = False',
    text
)

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")
