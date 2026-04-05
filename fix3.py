with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''        elif "text-to-video" in endpoint_lower:
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution)
            _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "size", str(explicit_size).strip() if explicit_size is not None else None)
            _set_audio_flags(payload)
        else:''',
'''        elif "text-to-video" in endpoint_lower:
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution)
            _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "size", str(explicit_size).strip() if explicit_size is not None else None)
            
            camera_fixed = _pick_tool_value("cameraFixed")
            if camera_fixed is not None:
                if "seedance" in endpoint_lower or "seedance" in model_lower:
                    payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
                else:
                    payload["cameraFixed"] = _normalize_bool(camera_fixed, False)
                    
            _set_audio_flags(payload)
        else:'''
)


text = text.replace(
'''            if resolved_last_frame and "/rhart-video-" in endpoint_lower:
                payload["lastImageUrl"] = resolved_last_frame
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution or "720p")
            _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "movementAmplitude", movement_amplitude)
            _set_audio_flags(payload)

        _set_runninghub_prompt_expansion_flag(payload)''',
'''            if resolved_last_frame and "/rhart-video-" in endpoint_lower:
                payload["lastImageUrl"] = resolved_last_frame
            
            payload["duration"] = normalized_video_duration
            _set_if_present(payload, "resolution", normalized_video_resolution or "720p")
            _set_if_present(payload, "aspectRatio", str(explicit_aspect_ratio).strip() if explicit_aspect_ratio else None)
            _set_if_present(payload, "movementAmplitude", movement_amplitude)
            
            camera_fixed = _pick_tool_value("cameraFixed")
            if camera_fixed is not None:
                if "seedance" in endpoint_lower or "seedance" in model_lower:
                    payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
                else:
                    payload["cameraFixed"] = _normalize_bool(camera_fixed, False)
                    
            _set_audio_flags(payload)

        _set_runninghub_prompt_expansion_flag(payload)'''
)

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done camera fixes!')
