with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix cameraFixed inside the payload building areas (3 spots)
text = text.replace(
'''            _set_if_present(payload, "cameraFixed", _pick_tool_value("cameraFixed"))''',
'''            camera_fixed = _pick_tool_value("cameraFixed")
            if camera_fixed is not None:
                if "seedance" in endpoint_lower or "seedance" in model_lower:
                    payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
                else:
                    payload["cameraFixed"] = _normalize_bool(camera_fixed, False)'''
)

# Fix generateAudio in _set_audio_flags
text = text.replace(
'''            else:
                if _pick_tool_value("generateAudio") is not None:
                    payload_obj["generateAudio"] = _normalize_bool(_pick_tool_value("generateAudio"), False)
                elif _pick_tool_value("audio") is not None:''',
'''            else:
                if "seedance" in endpoint_lower or "seedance" in model_lower:
                    av = _pick_tool_value("generateAudio") or _pick_tool_value("audio") or _pick_tool_value("sound")
                    payload_obj["generateAudio"] = "true" if _normalize_bool(av, False) else "false"
                elif _pick_tool_value("generateAudio") is not None:
                    payload_obj["generateAudio"] = _normalize_bool(_pick_tool_value("generateAudio"), False)
                elif _pick_tool_value("audio") is not None:'''
)

# Fix retry logic
text = text.replace(
'''                                    if field_name in ["generateAudio", "bgm", "audio", "sound"]:
                                        _debug_log(f"[{log_tag}] RunningHub missing field '{field_name}' detected '{submit_error_message}', automatically assigning False...", "warning")
                                        payload[field_name] = False
                                        await asyncio.sleep(min(2 * (submit_attempt + 1), 5))''',
'''                                    if field_name in ["generateAudio", "bgm", "audio", "sound", "cameraFixed"]:
                                        _debug_log(f"[{log_tag}] RunningHub missing field '{field_name}' detected '{submit_error_message}', automatically assigning False...", "warning")
                                        if field_name in ["generateAudio", "cameraFixed"] and ("seedance" in endpoint.lower() or "seedance" in model.lower()):
                                            payload[field_name] = "false"
                                        else:
                                            payload[field_name] = False
                                        await asyncio.sleep(min(2 * (submit_attempt + 1), 5))'''
)

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
