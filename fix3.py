import re

with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

handlers = [
    {'_name': '_handle_zlhub_generation', 'provider': 'zlhub', 'insert_before': r'(\s*)if re.match\(r\"\^https\?://\", endpoint'},
    {'_name': '_handle_vidu_generation', 'provider': 'vidu', 'insert_before': r'(\s*)def _normalize_bool'},
    {'_name': '_handle_apiyi_generation', 'provider': 'apiyi', 'insert_before': r'(\s*)provider_key = str\('},
    {'_name': '_handle_n1n_generation', 'provider': 'n1n', 'insert_before': r'(\s*)def _post_korea'},
    {'_name': '_handle_tencent_generation', 'provider': 'tencent', 'insert_before': r'(\s*)if gen_type == \"image\":'},
    {'_name': '_handle_wanxiang_generation', 'provider': 'wanxiang', 'insert_before': r'(\s*)if gen_type == \"video\":|elif gen_type == \"video\":'},
    {'_name': '_handle_aiclub_generation', 'provider': 'aiclub', 'insert_before': r'(\s*)if not str\(endpoint\)\.startswith'},
    {'_name': '_handle_stability_generation', 'provider': 'stability', 'insert_before': r'(\s*)# I2I'}
]

for h in handlers:
    idx = text.find(h['_name'])
    if idx == -1: continue
    if '_resolve_provider_callback_url' not in text[idx:idx+2500]:
        m = re.search(h['insert_before'], text[idx:idx+3000])
        if m:
            insert_idx = idx + m.start()
            ind = m.group(1)
            # Remove newline from ind if any
            ind = ind.replace('\n', '')
            
            inj =  ind + 'raw_callback_url = str(tool_conf.get("_provider_callback_url") or tool_conf.get("webhookUrl") or tool_conf.get("webHook") or tool_conf.get("webhook") or tool_conf.get("callBackUrl") or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or "").strip()\n'
            inj += ind + f'callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or f"{h["provider"]}-{{gen_type}}"\n'
            inj += ind + 'callback_tool_conf = dict(tool_conf or {})\n'
            inj += ind + 'if raw_callback_url:\n'
            inj += ind + '    callback_tool_conf.setdefault("callback_url", raw_callback_url)\n'
            inj += ind + 'callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)\n\n'
            
            text = text[:insert_idx] + '\n' + inj + text[insert_idx:]
            print('fixed', h['_name'])

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

