import os

with open('ark_seedance.txt', 'r', encoding='utf-8') as f:
    original = f.read()

new_code = '''    async def _handle_ark_seedance_generation(self, category: str, prompt: str, config: dict, reference_image_url: str = None, duration=None, aspect_ratio=None) -> dict:
        api_key = config.get("api_key", "")
        ak, sk, dp_token = "", "", ""
        if ":" in api_key and api_key.count(":") >= 2:
            parts = api_key.split(":", 2)
            ak = parts[0]
            sk = parts[1]
            dp_token = parts[2]
        else:
            return {"error": "ark-seedance provider requires api_key format: AK:SK:EP_TOKEN"}
            
        ref_image = reference_image_url
        if not ref_image:
            return {"error": "seedance 2.0 requires an image reference"}
            
        import base64
        import json
        import aiohttp
        
        img_b64 = ""
        if str(ref_image).startswith("http"):
            import requests
            img_b64 = base64.b64encode(requests.get(ref_image).content).decode("utf-8")
        else:
            marker = ";base64,"
            idx = ref_image.find(marker)
            if idx != -1:
                img_b64 = ref_image[idx + len(marker):].strip()
            else:
                img_b64 = ref_image
                
        try:
            group_res = self._do_volc_request("POST", "CreateAssetGroup", "2024-01-01", "{}", "ark", ak, sk)
            asset_group_id = group_res.get("AssetGroupId")
            if not asset_group_id:
                return {"error": f"Failed to create AssetGroupId: {group_res}"}
                
            asset_payload = json.dumps({
                "AssetGroupId": asset_group_id,
                "Type": "image",
                "Data": img_b64
            })
            asset_res = self._do_volc_request("POST", "CreateAsset", "2024-01-01", asset_payload, "ark", ak, sk)
            asset_id = asset_res.get("Asset", {}).get("AssetId")
            if not asset_id:
                return {"error": f"Failed to create Asset: {asset_res}"}
                
            import time
            import asyncio
            max_polls = 20
            ready = False
            for _ in range(max_polls):
                await asyncio.sleep(2)
                poll_req = json.dumps({"AssetId": asset_id})
                poll_res = self._do_volc_request("POST", "GetAsset", "2024-01-01", poll_req, "ark", ak, sk)
                status = poll_res.get("Asset", {}).get("Status", "processing")
                if status == "ready":
                    ready = True
                    break
                if status == "failed":
                    return {"error": f"Asset upload failed during polling: {poll_res}"}
                    
            if not ready:
                return {"error": "Timed out waiting for Ark asset to become ready"}
                
            bot_endpoint = "https://ark.cn-beijing.volces.com/api/v3/bots/chat/completions"
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
            gen_res = requests.post(bot_endpoint, headers=chat_headers, json=chat_payload)
            r_json = gen_res.json()
            
            if "error" in r_json:
                return {"error": r_json["error"], "response": r_json}
                
            return {
                "process_id": r_json.get("id", f"ark_seedance_{asset_id}"),
                "raw_response": r_json,
                "result": r_json
            }
        except Exception as e:
            import traceback
            _debug_log(f"ark-seedance exception: {e}\\n{traceback.format_exc()}", "error")
            return {"error": str(e)}
'''

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

if original in text:
    text = text.replace(original, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Replaced successfully!")
else:
    print("Original not found in file!")
