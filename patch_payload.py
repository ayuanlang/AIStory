with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('payload: Dict[str, Any] = {')
if idx != -1:
    end = text.find('}', idx)
    inj = '\n        if callback_url and callback_url != "-1":\n            payload["callBackUrl"] = callback_url\n'
    text = text[:end+1] + inj + text[end+1:]

idx2 = text.find('def _handle_vidu_generation')
if idx2 != -1:
    idx3 = text.find('payload = {', idx2)
    end3 = text.find('}', idx3)
    inj3 = '\n            if callback_url and callback_url != "-1":\n                payload["webhookUrl"] = callback_url\n'
    text = text[:end3+1] + inj3 + text[end3+1:]

idx4 = text.find('def _handle_apiyi_generation')
if idx4 != -1:
    idx5 = text.find('base_metadata = {', idx4)
    if idx5 != -1:
        inj4 = '        if callback_url and callback_url != "-1":\n            payload["webhookUrl"] = callback_url\n'
        text = text[:idx5] + inj4 + text[idx5:]

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
