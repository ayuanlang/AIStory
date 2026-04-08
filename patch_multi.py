def main():
    with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
        text = f.read()

    replacement = '''        elif "multimodal-video" in endpoint_lower:
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
            
            _set_audio_flags(payload)
        elif "start-end-to-video" in endpoint_lower or "start-to-end" in endpoint_lower:'''

    if 'elif "multimodal-video" in endpoint_lower:' not in text:
        text = text.replace('        elif "start-end-to-video" in endpoint_lower or "start-to-end" in endpoint_lower:', replacement)

    durations = '''("/openapi/v2/rhart-video/sparkvideo", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/rhart-video/sparkvideo-2.0-fast/multimodal-video", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/rhart-video/sparkvideo-2.0/multimodal-video", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),'''

    if 'sparkvideo-2.0/multimodal-video' not in text:
        text = text.replace('("/openapi/v2/rhart-video/sparkvideo", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),', durations)

    with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
        f.write(text)

    print('Payload injected.')

if __name__ == '__main__':
    main()
