import re

with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Define targeted replacement functions

def apply_patch(func_name, provider_name, url_key, payload_str="payload", webhook_field="webhookUrl"):
    global text
    idx = text.find(f"async def {func_name}")
    if idx == -1: return
    idx2 = text.find("async def _handle_", idx + 10)
    if idx2 == -1: idx2 = len(text)
    
    chunk = text[idx:idx2]
    
    # 1. Add resolver if missing
    if "_resolve_provider_callback_url" not in chunk:
        target = 'tool_conf = config.get("config", {}) or {}'
        inj1 = f'''
        raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"{provider_name}-{{gen_type}}"
        callback_tool_conf = dict(tool_conf or {{}})
        if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
'''
        if target in chunk:
            chunk = chunk.replace(target, target + inj1, 1)

    # 2. Add payload assignment
    # We find the main payload dict and inject it
    if "callback_url and callback_url !=" not in chunk:
        # Simplistic approach: find where payload is used, right before requests.post/submit_and_poll
        inj2 = f'''
        if callback_url and callback_url != "-1":
            {payload_str}["{webhook_field}"] = callback_url
'''
        if payload_str in chunk:
            # specifically for ZLHub "seedance2_payload_mode"
            if provider_name == 'zlhub':
                t2 = 'payload: Dict[str, Any] = {'
                chunk = chunk.replace(t2, t2 + inj2, 1)
            elif provider_name == 'vidu':
                # Replace right before the poll loop or post
                t2 = 'payload = {'
                chunk = chunk.replace(t2, t2 + inj2, 1)
            elif provider_name == 'apiyi':
                t2 = 'base_metadata = {'
                chunk = chunk.replace(t2, inj2 + '        ' + t2, 1)

    text = text[:idx] + chunk + text[idx2:]
    print(f"Patched {func_name}")

apply_patch('_handle_zlhub_generation', 'zlhub', 'callBackUrl', 'payload', 'callBackUrl')
apply_patch('_handle_vidu_generation', 'vidu', 'webhookUrl', 'payload', 'webhookUrl')
apply_patch('_handle_apiyi_generation', 'apiyi', 'webhookUrl', 'payload', 'webhookUrl')
apply_patch('_handle_aiclub_generation', 'aiclub', 'webhookUrl', 'payload', 'webhookUrl')

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

