def patch8():
    with open('../backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
        text = f.read()

    lines = text.split('\n')
    idx = [i for i, l in enumerate(lines) if 'if not line.startswith("data:"):' in l][0]
    
    # insert before
    code = """                        if not line.startswith("data:") and line != "[DONE]" and len(line) > 0 and "heartbeat" not in line and "{" in line:
                            logger.warning(f"Unexpected non-SSE line in LLM stream: {line[:200]}")"""

    lines.insert(idx, code)
    
    with open('../backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

patch8()