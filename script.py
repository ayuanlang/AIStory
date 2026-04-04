import re

with open(r"c:\AIStory\backend\app\services\media_service.py", "r", encoding="utf-8") as f:
    content = f.read()

target_code = """
                    if isinstance(polled_data, dict):
                        inner = polled_data.get("data", {}) if isinstance(polled_data.get("data"), dict) else {}
                        status_val = polled_data.get("status") or inner.get("status") or inner.get("taskStatus")
                        print(f"[AIClub Polling] attempt={attempt} url={poll_url} data={polled_data}")
                        
                        url_candidates = [
                            polled_data.get("url"), inner.get("url"),
                            inner.get("resultUrl"), polled_data.get("resultUrl"),
                            inner.get("videoUrl"), polled_data.get("videoUrl"),
                            inner.get("imageUrl"), polled_data.get("imageUrl"),
                            polled_data.get("image_url"), inner.get("image_url"),
                            polled_data.get("video_url"), inner.get("video_url")
                        ]
                        result_url = next((u for u in url_candidates if isinstance(u, str) and u), None)
                        
                        if not result_url:
                            for coll in ["images", "videos", "results"]:
                                items = inner.get(coll) or polled_data.get(coll) or []
                                if isinstance(items, list) and items:
                                    first = items[0]
                                    if isinstance(first, dict):
                                        result_url = first.get("url") or first.get("imageUrl") or first.get("videoUrl") or first.get("resultUrl")
                                    elif isinstance(first, str):
                                        result_url = first
                                    if result_url: break

                        if str(status_val).upper() in ["SUCCESS", "SUCCESSFUL", "COMPLETED", "200"]:
                            if result_url: return {"url": result_url, "metadata": base_metadata}
                            else: return {"error": f"No URL inside SUCCESS response: {polled_data}", "submit_failed": False}

                        if str(status_val).upper() in ["FAILED", "ERROR", "CANCELED", "CANCELLED"]:
"""

replacement_code = """
                    if isinstance(polled_data, dict):
                        inner = polled_data.get("data", {}) if isinstance(polled_data.get("data"), dict) else {}
                        info = inner.get("info", {}) if isinstance(inner.get("info"), dict) else {}
                        status_val = polled_data.get("status") or inner.get("status") or inner.get("taskStatus") or info.get("status") or polled_data.get("state")
                        print(f"[AIClub Polling] attempt={attempt} url={poll_url} data={polled_data}")
                        
                        url_candidates = [
                            polled_data.get("url"), inner.get("url"), info.get("url"),
                            inner.get("resultUrl"), polled_data.get("resultUrl"), info.get("resultUrl"),
                            inner.get("videoUrl"), polled_data.get("videoUrl"), info.get("videoUrl"),
                            inner.get("imageUrl"), polled_data.get("imageUrl"), info.get("imageUrl"),
                            polled_data.get("image_url"), inner.get("image_url"), info.get("image_url"),
                            polled_data.get("video_url"), inner.get("video_url"), info.get("video_url"),
                            info.get("resultImageUrl"), info.get("resultVideoUrl")
                        ]
                        result_url = next((u for u in url_candidates if isinstance(u, str) and u), None)
                        
                        if not result_url:
                            for coll in ["images", "videos", "results", "video_url"]:
                                items = inner.get(coll) or polled_data.get(coll) or info.get(coll) or []
                                if isinstance(items, list) and items:
                                    first = items[0]
                                    if isinstance(first, dict):
                                        result_url = first.get("url") or first.get("imageUrl") or first.get("videoUrl") or first.get("resultUrl")
                                    elif isinstance(first, str):
                                        result_url = first
                                    if result_url: break
                                    
                        if result_url and not status_val:
                            # For endpoints where no explicit success status is given, presence of URL indicates success
                            status_val = "SUCCESS"

                        if str(status_val).upper() in ["SUCCESS", "SUCCESSFUL", "COMPLETED", "200"]:
                            if result_url: return {"url": result_url, "metadata": base_metadata}
                            else: return {"error": f"No URL inside SUCCESS response: {polled_data}", "submit_failed": False}

                        if str(status_val).upper() in ["FAILED", "ERROR", "CANCELED", "CANCELLED"]:
"""

content = content.replace(target_code, replacement_code)
with open(r"c:\AIStory\backend\app\services\media_service.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Replaced!")
