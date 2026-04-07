with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

handlers = [
    {'_name': '_handle_n1n_generation', 'provider': 'n1n', 'insert_before': 'headers = {"Authorization"'},
    {'_name': '_handle_aiclub_generation', 'provider': 'aiclub', 'insert_before': 'headers = {"Authorization"'}
]

for h in handlers:
    idx = text.find(h['_name'])
    if idx != -1 and '_resolve_provider_callback_url' not in text[idx:idx+2500]:
        insert_idx = text.find(h['insert_before'], idx)
        if insert_idx != -1:
            ls = text.rfind('\n', 0, insert_idx)
            ind = text[ls+1:insert_idx]
            inj = ind + 'raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()\n'
            inj += ind + f'callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"{{h[\"provider\"]}}-{{gen_type}}"\n'
            inj += ind + 'callback_tool_conf = dict(tool_conf or {})\n'
            inj += ind + 'if raw_callback_url: callback_tool_conf.setdefault("callback_url", raw_callback_url)\n'
            inj += ind + 'callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)\n\n'
            
            text = text[:ls+1] + inj + ind + text[insert_idx:]
            print('injected into', h['_name'])

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
