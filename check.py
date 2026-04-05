with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

count1 = text.count('av = _pick_tool_value("generateAudio")')
count2 = text.count('camera_fixed is not None')
count3 = text.count('field_name in ["generateAudio", "cameraFixed"]')
print('Audio fixes:', count1, 'Camera fixes:', count2, 'Retry logic:', count3)
