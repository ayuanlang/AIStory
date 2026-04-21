import re

def main():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        text = f.read()

    old_s = '''        payload = {
            "raw": body_bytes.decode("utf-8", errors="ignore") if body_bytes else "",
            "content_type": str(request.headers.get("content-type") or "").strip(),
        }

    _verify_kie_webhook_request(request, payload if isinstance(payload, dict) else {})'''
    
    new_s = '''        payload = {
            "raw": body_bytes.decode("utf-8", errors="ignore") if body_bytes else "",
            "content_type": str(request.headers.get("content-type") or "").strip(),
        }

    import json
    try:
        dump_str = json.dumps(payload, ensure_ascii=False)
        client_host = getattr(getattr(request, "client", None), "host", "Unknown")
        
        logger.info("=" * 60)
        logger.info(f"🔔 [WEBHOOK CALLBACK RECEIVED] [{client_host}] Ticket: {stable_ticket}")
        if len(dump_str) > 2000:
            logger.info(f"🔔 [WEBHOOK PAYLOAD] {dump_str[:2000]}...(truncated)")
        else:
            logger.info(f"🔔 [WEBHOOK PAYLOAD] {dump_str}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Failed to log webhook payload: {e}")

    _verify_kie_webhook_request(request, payload if isinstance(payload, dict) else {})'''

    if old_s in text:
        text = text.replace(old_s, new_s, 1)
        with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Updated endpoint callback logging.")
    else:
        print("Could not find the target string in endpoints.py.")

if __name__ == '__main__':
    main()
