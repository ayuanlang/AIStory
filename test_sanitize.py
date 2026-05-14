import sys
import os

# add backend app to path
sys.path.append(r'c:\AS\AIStory\backend')
from app.services.media_service import MediaGenerationService

media_service = MediaGenerationService()

text = "在 @Image1 ENV:[冷宫偏殿]"
print("Original:", text)

# Test kie
kie_res = media_service._sanitize_kie_prompt_mentions(text, {})
print("KIE:", kie_res)

# Test sora
sora_res = media_service._sanitize_sora_prompt_mentions(text)
print("SORA:", sora_res)

# What if text has no space?
text2 = "在 @Image1ENV:[冷宫偏殿]"
print("Original2:", text2)
print("KIE2:", media_service._sanitize_kie_prompt_mentions(text2, {}))

