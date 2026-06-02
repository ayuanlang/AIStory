import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'    async def _handle_ark_seedance_generation[\s\S]*?(?=    async def |    def |$)', text)
if m:
    original = m.group(0)
    
    old_code_block = """            _debug_log(f"Submitting seedance 2.0 generation (task create) -> {task_endpoint}", "info")
            import requests
            gen_res = requests.post(task_endpoint, headers=task_headers, json=task_payload)
            r_json = gen_res.json()
            
            if "error" in r_json:
                return {"error": r_json["error"], "response": r_json}
                
            return {
                "process_id": r_json.get("id", f"ark_seedance_{asset_id}"),
                "raw_response": r_json,
                "result": r_json
            }"""

    new_code_block = """            _debug_log(f"Submitting seedance 2.0 generation (task create) -> {task_endpoint}", "info")
            extra_metadata = {"provider": "ark-seedance", "model": model_id}
            
            return await self._submit_and_poll_video(
                url=task_endpoint,
                payload=task_payload,
                api_key=dp_token,
                log_tag="ark-seedance",
                extra_metadata=extra_metadata,
                poll_timeout_seconds=300
            )"""
            
    if old_code_block in text:
        new_text = text.replace(old_code_block, new_code_block)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        print("Success! Patched media_service content_generation.")
    else:
        print("Old block not found.")
else:
    print("Method not found.")
