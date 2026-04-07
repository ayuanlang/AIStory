import re
with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

def patch_handler(name, provider, webhook_key):
    global text
    idx = text.find(f'def {name}')
    if idx == -1: return
    idx2 = text.find('async def _handle_', idx+10)
    if idx2 == -1: idx2 = len(text)
    
    chunk = text[idx:idx2]
    if '_resolve_provider_callback_url' not in chunk:
        # inject resolver snippet right after tool_conf
        target = 'tool_conf = config.get("config", {}) or {}'
        insert_idx = chunk.find(target)
        if insert_idx != -1:
            end_idx = insert_idx + len(target)
            inj = f'''
        raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"{provider}-{{gen_type}}"
        callback_tool_conf = dict(tool_conf or {{}})
        if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)'''
            chunk = chunk[:end_idx] + inj + chunk[end_idx:]
            text = text[:idx] + chunk + text[idx2:]
            print(f"Patched config for {name}")

patch_handler('_handle_zlhub_generation', 'zlhub', 'callBackUrl')
patch_handler('_handle_vidu_generation', 'vidu', 'webhookUrl')
patch_handler('_handle_apiyi_generation', 'apiyi', 'webhookUrl')
patch_handler('_handle_aiclub_generation', 'aiclub', 'webhookUrl')

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

