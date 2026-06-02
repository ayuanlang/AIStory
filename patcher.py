import os

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """                elif effective_provider == "doubao":
                    runtime_result = await self._handle_doubao_generation(
                        "video",
                        prompt,
                        active_config,
                        reference_image_url=effective_reference_image_url,
                        duration=effective_duration,
                    )"""

replacement = target + """
                elif effective_provider == "ark-seedance":
                    runtime_result = await self._handle_ark_seedance_generation(
                        "video",
                        prompt,
                        active_config,
                        effective_reference_image_url,
                        duration=effective_duration,
                        aspect_ratio=effective_aspect_ratio,
                    )"""

if target in text:
    new_text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched!")
else:
    print("Not found.")
