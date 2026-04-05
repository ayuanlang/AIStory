with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = '''            camera_fixed = _pick_tool_value("cameraFixed")
            if camera_fixed is not None:
                if "seedance" in endpoint_lower or "seedance" in model_lower:
                    payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
                else:
                    payload["cameraFixed"] = _normalize_bool(camera_fixed, False)'''

new_block = '''            camera_fixed = _pick_tool_value("cameraFixed")
            if "seedance" in endpoint_lower or "seedance" in model_lower:
                payload["cameraFixed"] = "true" if _normalize_bool(camera_fixed, False) else "false"
            elif camera_fixed is not None:
                payload["cameraFixed"] = _normalize_bool(camera_fixed, False)'''

if old_block in text:
    print('Found old block!')
    text = text.replace(old_block, new_block)
    with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
        f.write(text)
else:
    print('Block not found!')
