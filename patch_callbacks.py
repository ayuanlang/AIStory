import re
with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

def patch_handler(name, provider, target_pattern, payload_pattern, webhook_key):
    global text
    idx = text.find(f'def {name}')
    if idx == -1: return
    idx2 = text.find('async def _handle_', idx+10)
    if idx2 == -1: idx2 = len(text)
    
    chunk = text[idx:idx2]
    if '_resolve_provider_callback_url' not in chunk:
        # inject resolver snippet
        def repl1(m):
            return m.group(0) + f'''
        raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"{provider}-{{gen_type}}"
        callback_tool_conf = dict(tool_conf or {{}})
        if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
'''
        chunk = re.sub(target_pattern, repl1, chunk, count=1)
        
        # inject payload assignment
        def repl2(m):
            return m.group(0) + f'''
            if callback_url and callback_url != "-1":
                {m.group(1)}["{webhook_key}"] = callback_url
'''
        chunk = re.sub(payload_pattern, repl2, chunk, count=1)
        text = text[:idx] + chunk + text[idx2:]
        print(f"Patched {name}")

patch_handler('_handle_zlhub_generation', 'zlhub', r'tool_conf = config\.get\("config", \{\}\) or \{\}.*?\n', r'(payload(?:\s*:\s*[A-Za-z\[\]\s,]+)?)\s*=\s*\{.*?\}(?:\s*\n)*\s*payload(?:\[[^\]]+\]\s*=\s*[^\n]+?\n)*', 'callBackUrl')
patch_handler('_handle_vidu_generation', 'vidu', r'tool_conf = config\.get\("config", \{\}\) or \{\}.*?\n', r'(payload(?:\s*:\s*[A-Za-z\[\]\s,]+)?)\s*=\s*\{[^\}]+\}\s*\n', 'webhookUrl')
patch_handler('_handle_apiyi_generation', 'apiyi', r'tool_conf = config\.get\("config", \{\}\) or \{\}.*?\n', r'(payload(?:\s*:\s*[A-Za-z\[\]\s,]+)?)\s*=\s*\{[^\}]+\}\s*\n', 'webhookUrl')

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

