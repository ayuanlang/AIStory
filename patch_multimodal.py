def main():
    with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
        text = f.read()

    to_replace = '        elif "start-end-to-video" in endpoint_lower or "start-to-end" in endpoint_lower:'

    replacement = '''        elif "multimodal-video" in endpoint_lower:
            payload["imageUrls"] = image_refs[:9]
            payload["videoUrls"] = video_refs[:3] if video_refs else []
                
            audio_refs = _pick_tool_value("audioUrls") or []
            if isinstance(audio_refs, str): audio_refs = [audio_refs]
            payload["audioUrls"] = audio_refs[:3]
            
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution or "720p")
            _set_if_present(payload, "ratio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "realPersonMode", True)
            
            _set_audio_flags(payload)
        elif "start-end-to-video" in endpoint_lower or "start-to-end" in endpoint_lower:'''

    text = text.replace(to_replace, replacement)

    with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
        f.write(text)

    print('Patched successfully!')

if __name__ == '__main__':
    main()
