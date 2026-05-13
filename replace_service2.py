import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_str = """        elif "multimodal-video" in endpoint_lower:
            payload["imageUrls"] = image_refs[:9]
            if video_refs:
                payload["videoUrls"] = video_refs[:3]
            else:
                payload["videoUrls"] = []
                
            audio_refs = _pick_tool_value("audioUrls") or []
            if isinstance(audio_refs, str): audio_refs = [audio_refs]
            payload["audioUrls"] = audio_refs[:3]
            
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution or "720p")
            _set_if_present(payload, "ratio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "realPersonMode", True)
            
            _set_audio_flags(payload)"""

new_str = """        elif "multimodal-video" in endpoint_lower:
            payload["imageUrls"] = image_refs[:9]
            if video_refs:
                payload["videoUrls"] = video_refs[:3]
            else:
                payload["videoUrls"] = []
                
            audio_refs = _pick_tool_value("audioUrls") or []
            if isinstance(audio_refs, str): audio_refs = [audio_refs]
            payload["audioUrls"] = audio_refs[:3]
            
            payload["duration"] = str(normalized_video_duration) if normalized_video_duration else "5"
            _set_if_present(payload, "resolution", normalized_video_resolution or "720p")
            _set_if_present(payload, "ratio", "adaptive" if not explicit_aspect_ratio else str(explicit_aspect_ratio).strip())
            _set_if_present(payload, "realPersonMode", True)
            payload["conversionSlots"] = ["all"]
            payload["returnLastFrame"] = False
            
            _set_audio_flags(payload)"""

if old_str in content:
    content = content.replace(old_str, new_str)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced string block successfully!")
else:
    # try regex
    match = re.search(r'elif "multimodal-video" in endpoint_lower:.*?_set_audio_flags\(payload\)', content, re.DOTALL)
    if match:
        content = content[:match.start()] + new_str.strip() + content[match.end():]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Replaced using regex!")
    else:
        print("Not found at all!")
