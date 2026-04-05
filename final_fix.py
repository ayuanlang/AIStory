import re

with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Fix _set_audio_flags
text = re.sub(
    r'                if "seedance" in endpoint_lower or "seedance" in model_lower:\n                    av = _pick_tool_value\("generateAudio"\) or _pick_tool_value\("audio"\) or _pick_tool_value\("sound"\)\n                    payload_obj\["generateAudio"\] = "true" if _normalize_bool\(av, False\) else "false"\n                elif _pick_tool_value\("generateAudio"\) is not None:\n                    payload_obj\["generateAudio"\] = _normalize_bool\(_pick_tool_value\("generateAudio"\), False\)\n                elif _pick_tool_value\("audio"\) is not None:\n                    payload_obj\["audio"\] = _normalize_bool\(_pick_tool_value\("audio"\), False\)\n                elif _pick_tool_value\("sound"\) is not None:\n                    payload_obj\["sound"\] = _normalize_bool\(_pick_tool_value\("sound"\), False\)\n                elif _pick_tool_value\("bgm"\) is not None:\n                    payload_obj\["bgm"\] = _normalize_bool\(_pick_tool_value\("bgm"\), True\)',
    '                if "seedance" in endpoint_lower or "seedance" in model_lower:\n                    av = _pick_tool_value("generateAudio") or _pick_tool_value("audio") or _pick_tool_value("sound")\n                    payload_obj["generateAudio"] = "true" if _normalize_bool(av, False) else "false"\n                elif _pick_tool_value("generateAudio") is not None:\n                    payload_obj["generateAudio"] = _normalize_bool(_pick_tool_value("generateAudio"), False)\n                elif _pick_tool_value("audio") is not None:\n                    payload_obj["audio"] = _normalize_bool(_pick_tool_value("audio"), False)\n                elif _pick_tool_value("sound") is not None:\n                    payload_obj["sound"] = _normalize_bool(_pick_tool_value("sound"), False)\n                elif _pick_tool_value("bgm") is not None:\n                    payload_obj["bgm"] = _normalize_bool(_pick_tool_value("bgm"), True)',
    text
)

# 2. Fix cameraFixed (3 times)
for i in range(5):
    text = re.sub(
        r'            camera_fixed = _pick_tool_value\("cameraFixed"\)\n            if "seedance" in endpoint_lower or "seedance" in model_lower:\n                payload\["cameraFixed"\] = "true" if _normalize_bool\(camera_fixed, False\) else "false"\n            elif camera_fixed is not None:\n                payload\["cameraFixed"\] = _normalize_bool\(camera_fixed, False\)',
        '            camera_fixed = _pick_tool_value("cameraFixed")\n            if "seedance" in endpoint_lower or "seedance" in model_lower:\n                payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"\n            elif camera_fixed is not None:\n                payload["cameraFixed"] = _normalize_bool(camera_fixed, False)',
        text
    )
    
    text = re.sub(
        r'            camera_fixed = _pick_tool_value\("cameraFixed"\)\n            if camera_fixed is not None:\n                payload\["cameraFixed"\] = _normalize_bool\(camera_fixed, False\)',
        '            camera_fixed = _pick_tool_value("cameraFixed")\n            if "seedance" in endpoint_lower or "seedance" in model_lower:\n                payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"\n            elif camera_fixed is not None:\n                payload["cameraFixed"] = _normalize_bool(camera_fixed, False)',
        text
    )
    
    text = re.sub(
        r'            camera_fixed = _pick_tool_value\("cameraFixed"\)\n            payload\["cameraFixed"\] = "true" if _normalize_bool\(camera_fixed, False\) else "false"',
        '            camera_fixed = _pick_tool_value("cameraFixed")\n            if "seedance" in endpoint_lower or "seedance" in model_lower:\n                payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"\n            elif camera_fixed is not None:\n                payload["cameraFixed"] = _normalize_bool(camera_fixed, False)',
        text
    )

# 3. Fix Retry Logic
text = re.sub(
    r'if field_name in \["generateAudio", "cameraFixed"\] and \("seedance" in endpoint.lower\(\) or "seedance" in model.lower\(\)\):',
    r'if field_name in ["generateAudio", "cameraFixed"] and ("seedance" in submit_url.lower() or "seedance" in str(payload.get("model", "")).lower()):',
    text
)

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")
