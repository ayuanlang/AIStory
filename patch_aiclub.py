import re
path = r'c:\AIStory\backend\app\services\media_service.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

pattern = r'        base_metadata = \{\n            "provider": provider_name,\n            "model": model,\n            "prompt": prompt,\n            "submit_url": submit_url,\n        \}\n\n        return await self\._submit_and_poll_video[^\n]*\n\n    def _extract_zlhub_task_id'

replacement = '''        base_metadata = {
            "provider": provider_name,
            "model": model,
            "prompt": prompt,
            "submit_url": submit_url,
        }

        # Submitting the task
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            resp = await asyncio.to_thread(requests.post, submit_url, json=payload, headers=headers, timeout=(15, 60), verify=False)
            data = resp.json() if resp.text else {}
            if resp.status_code not in [200, 201]:
                return {"error": f"Submission Failed {resp.status_code}", "details": data, "submit_failed": True}
        except Exception as e:
            return {"error": f"Submission Exception: {e}", "submit_failed": True}

        # Check for immediate url in response
        if isinstance(data, dict):
            if "url" in data:
                return {"url": data["url"], "metadata": base_metadata}
            elif "data" in data and isinstance(data["data"], dict):
                if "url" in data["data"]:
                    return {"url": data["data"]["url"], "metadata": base_metadata}

        # Extract task_id
        task_id = None
        if isinstance(data, dict):
            task_id = data.get("id") or data.get("task_id") or data.get("taskId")
            if not task_id and "data" in data and isinstance(data["data"], dict):
                inner = data["data"]
                task_id = inner.get("taskId") or inner.get("task_id") or inner.get("id")

        if not task_id:
            return {"error": f"No Task ID or URL returned: {data}", "submit_failed": True}

        # Polling
        # Because we might not know if it needs a slash tasks, etc., let's use the reference
        # The reference shows GET /model/openApi/nanoBanana/v1/tasks/{taskId} or GET /model/openApi/nanoBanana/v1/tasks/ (which lists tasks)
        # Assuming it needs /tasks/{task_id}
        base_route = f"{base_url}/nanoBanana/v1" if "gemini" in model.lower() else f"{base_url}/{model}/v1"
        poll_url = f"{base_route}/tasks/{task_id}"

        max_attempts = 150
        for attempt in range(max_attempts):
            await asyncio.sleep(2)
            try:
                poll_resp = await asyncio.to_thread(
                    requests.get,
                    poll_url,
                    headers=headers,
                    timeout=30,
                    verify=False
                )
                if poll_resp.status_code in [200, 201] and poll_resp.text:
                    polled_data = poll_resp.json()
                    status_val = None
                    result_url = None
                    
                    if isinstance(polled_data, dict):
                        inner = polled_data.get("data", {}) if isinstance(polled_data.get("data"), dict) else {}
                        status_val = polled_data.get("status") or inner.get("status") or inner.get("taskStatus")
                        result_url = polled_data.get("url") or inner.get("url") or inner.get("resultUrl") or polled_data.get("resultUrl")

                        if str(status_val).upper() in ["SUCCESS", "SUCCESSFUL", "COMPLETED", "200"]:
                            if result_url:
                                return {"url": result_url, "metadata": base_metadata}
                            else:
                                return {"error": f"No URL inside SUCCESS response: {polled_data}", "submit_failed": False}

                        if str(status_val).upper() in ["FAILED", "ERROR", "CANCELED", "CANCELLED"]:
                            err_msg = inner.get("reason") or inner.get("error") or polled_data.get("message") or "Unknown error"
                            return {"error": f"Generation failed: {err_msg}", "details": polled_data, "submit_failed": False}

            except Exception as pe:
                if attempt == max_attempts - 1:
                    return {"error": f"Polling Exception: {pe}", "submit_failed": False}
                
        return {"error": "Polling Timeout", "submit_failed": False}

    def _extract_zlhub_task_id'''

new_code, c = re.subn(pattern, replacement, code, flags=re.MULTILINE)
if c:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_code)
    print('Replaced ' + str(c))
else:
    print('Pattern not found')
