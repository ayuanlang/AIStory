import sys
import re

p1 = 'c:/AS/AIStory/backend/app/services/media_service.py'
with open(p1, 'r', encoding='utf-8') as f:
    text1 = f.read()

text1 = text1.replace('tool_conf["sound"] = False', 'tool_conf["sound"] = True')
text1 = text1.replace('payload_input_obj["sound"] = False', 'payload_input_obj["sound"] = True')

with open(p1, 'w', encoding='utf-8') as f:
    f.write(text1)

p2 = 'c:/AS/AIStory/backend/app/api/endpoints.py'
with open(p2, 'r', encoding='utf-8') as f:
    text2 = f.read()

text2 = text2.replace('resolved_sound = False', 'resolved_sound = True')

with open(p2, 'w', encoding='utf-8') as f:
    f.write(text2)

print("Done phase 2")
