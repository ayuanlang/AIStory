import sys
import re

p1 = 'c:/AS/AIStory/backend/app/services/media_service.py'
with open(p1, 'r', encoding='utf-8') as f:
    text1 = f.read()

# in media_service.py
text1 = text1.replace('payload_obj["sound"] = _normalize_bool(_pick_tool_value("sound"), False)', 'payload_obj["sound"] = True')
text1 = text1.replace('payload_obj["generateAudio"] = "true" if _normalize_bool(av, False) else "false"', 'payload_obj["generateAudio"] = "true"')
text1 = text1.replace('payload_obj["generateAudio"] = _normalize_bool(_pick_tool_value("generateAudio"), False)', 'payload_obj["generateAudio"] = True')
text1 = text1.replace('payload_obj["audio"] = _normalize_bool(_pick_tool_value("audio"), False)', 'payload_obj["audio"] = True')
text1 = text1.replace('payload_obj["audio"] = _normalize_bool(av, False)', 'payload_obj["audio"] = True')

# Replace sound generation payload assignment if av is not None ...
text1 = re.sub(r'payload_obj\["generateAudio"\] = _normalize_bool\(av, False\)', 'payload_obj["generateAudio"] = True', text1)


with open(p1, 'w', encoding='utf-8') as f:
    f.write(text1)

p2 = 'c:/AS/AIStory/backend/app/api/endpoints.py'
with open(p2, 'r', encoding='utf-8') as f:
    text2 = f.read()

text2 = re.sub(r'video_provider_options\["sound"\]\s*=\s*False', 'video_provider_options["sound"] = True', text2)
text2 = text2.replace('video_provider_options["sound"] = bool(resolved_sound)', 'video_provider_options["sound"] = True')
# Also check for config reading sound: False
text2 = text2.replace('if sound_capability is False:\n            video_provider_options["sound"] = False', 'if sound_capability is False:\n            video_provider_options["sound"] = True')

with open(p2, 'w', encoding='utf-8') as f:
    f.write(text2)

print("Done")