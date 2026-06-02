import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'    async def _handle_ark_seedance_generation[\s\S]*?(?=    async def |    def |$)', text)
if m:
    original_func = m.group(0)
    
    old_code_block = """            bot_endpoint = "https://ark.cn-beijing.volces.com/api/v3/bots/chat/completions"
            chat_payload = {
                "model": dp_token,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"asset://{asset_id}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            chat_headers = {
                "Authorization": f"Bearer {dp_token}",
                "Content-Type": "application/json"
            }
            
            _debug_log(f"Submitting seedance 2.0 generation -> {bot_endpoint}", "info")
            import requests
            gen_res = requests.post(bot_endpoint, headers=chat_headers, json=chat_payload)"""

    new_code_block = """            # Fire the generation task
            task_endpoint = "https://ark.cn-beijing.volces.com/api/v3/content_generation/tasks"
            
            model_id = config.get("model", "") # Get the model endpoint ID from config
            if not model_id or model_id in ["default", ""]:
                # If they leave it empty, use the generic default for seedance model
                model_id = "doubao-seedance-2-0-260128"
                
            task_payload = {
                "model": model_id,
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"asset://{asset_id}"
                        },
                        "role": "reference_image"
                    }
                ],
                "generate_audio": True,
                "watermark": True
            }
            
            if duration:
                try:
                    task_payload["duration"] = int(duration)
                except:
                    pass
            
            if aspect_ratio:
                task_payload["ratio"] = str(aspect_ratio)
                
            task_headers = {
                "Authorization": f"Bearer {dp_token}",
                "Content-Type": "application/json"
            }
            
            _debug_log(f"Submitting seedance 2.0 generation (task create) -> {task_endpoint}", "info")
            import requests
            gen_res = requests.post(task_endpoint, headers=task_headers, json=task_payload)"""

    if old_code_block in text:
        new_text = text.replace(old_code_block, new_code_block)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        print("Success! Patched media_service content_generation.")
    else:
        print("Old block not found.")
else:
    print("Method not found.")
