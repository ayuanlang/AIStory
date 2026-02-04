import os
import requests
import json
import base64
import time

# Mock Data
API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not API_KEY:
    print("Error: DASHSCOPE_API_KEY not found in environment.")
    # Attempt to read from settings if possible, but for DBG script rely on env
    # exit(1)

ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"

def run_debug():
    if not API_KEY:
        print("Skipping execution due to missing key.")
        return

    # Create a small blank image
    img_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
    b64_img = f"data:image/png;base64,{base64.b64encode(img_data).decode('utf-8')}"
    
    payload = {
        "model": "wanx2.1-kf2v-plus",
        "input": {
            "prompt": "A simple test video of a cat",
            "first_frame_url": b64_img,
            "last_frame_url": b64_img
        },
        "parameters": {
            "resolution": "720P",
            "prompt_extend": True
        }
    }
    
    headers = {
        "X-DashScope-Async": "enable",
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    print("--- Sending Request ---")
    print(json.dumps(payload, indent=2))
    
    try:
        resp = requests.post(ENDPOINT, json=payload, headers=headers, timeout=30, verify=False)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    run_debug()
