import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """            task_payload = {
                "model": model_id,
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": asset_id_or_url
                        },
                        "role": "reference_image"
                    }
                ],
                "generate_audio": True,
                "watermark": True
            }"""

replacement = """            # Ensure the prompt references the image to satisfy Volcengine requirement
            final_prompt = prompt
            if "图片" not in final_prompt and "素材" not in final_prompt:
                final_prompt = "图片1中，" + final_prompt

            task_payload = {
                "model": model_id,
                "content": [
                    {
                        "type": "text",
                        "text": final_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": asset_id_or_url
                        },
                        "role": "reference_image"
                    }
                ],
                "generate_audio": True,
                "watermark": True
            }"""

if target in text:
    new_text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched prompt image citation!")
else:
    print("Not found")