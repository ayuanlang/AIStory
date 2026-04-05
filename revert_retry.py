with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Revert retry logic for cameraFixed
text = re.sub(
    r'if field_name in \["generateAudio", "cameraFixed"\] and \("seedance" in submit_url.lower\(\) or "seedance" in str\(payload\.get\("model", ""\)\)\.lower\(\)\):\n\s*payload\[field_name\] = "false"',
    'if field_name == "generateAudio" and ("seedance" in submit_url.lower() or "seedance" in str(payload.get("model", "")).lower()):\n                                            payload[field_name] = "false"\n                                        elif field_name == "cameraFixed":\n                                            payload[field_name] = False',
    text
)

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
