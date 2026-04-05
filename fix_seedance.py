with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Fix retry logic 
text = re.sub(
    r'if field_name == "generateAudio" and \("seedance" in submit_url.lower\(\) or "seedance" in str\(payload\.get\("model", ""\)\)\.lower\(\)\):\n\s*payload\[field_name\] = "false"\n\s*elif field_name == "cameraFixed":\n\s*payload\[field_name\] = False\n\s*else:\n\s*payload\[field_name\] = False',
    'if field_name in ["generateAudio", "cameraFixed"] and ("seedance" in submit_url.lower() or "seedance" in str(payload.get("model", "")).lower()):\n                                            payload[field_name] = "false"\n                                        else:\n                                            payload[field_name] = False',
    text
)

# Fix video payload building for seedance
text = re.sub(
    r'camera_fixed\s*=\s*_pick_tool_value\("cameraFixed", field_args, False\)\s*payload\["cameraFixed"\]\s*=\s*_normalize_bool\(camera_fixed, False\)',
    'camera_fixed = _pick_tool_value("cameraFixed", field_args, False)\n        payload["cameraFixed"] = "false" if ("seedance" in str(video_model).lower() and not _normalize_bool(camera_fixed, False)) else ("true" if "seedance" in str(video_model).lower() else _normalize_bool(camera_fixed, False))',
    text
)


with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
