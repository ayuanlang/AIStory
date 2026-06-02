import os

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """                if effective_provider == "grsai":
                    return await self._handle_grsai_generation("video", prompt, active_config, effective_reference_image_url, last_frame_url=effective_last_frame_url, duration=effective_duration, aspect_ratio=effective_aspect_ratio, negative_prompt=negative_prompt)"""

replacement = target + """
                if effective_provider == "ark-seedance":
                    return await self._handle_ark_seedance_generation("video", prompt, active_config, effective_reference_image_url, duration=duration, aspect_ratio=aspect_ratio)"""

if target in text:
    new_text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched successfully!")
else:
    print("Target not found!")
