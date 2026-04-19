import sys

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    code = f.read()

target = '''    logger.info("Received analyze_scene request")
    try:
        logger.info(f"[analyze_scene] request.episode_id={getattr(request, 'episode_id', None)}")
    except Exception:
        pass'''

replacement = '''    logger.info("Received analyze_scene request")
    try:
        logger.info(f"[analyze_scene] request.episode_id={getattr(request, 'episode_id', None)}")
    except Exception:
        pass

    if not request.project_metadata and getattr(request, "episode_id", None):
        try:
            _auto_ep = db.query(Episode).filter(Episode.id == request.episode_id).first()
            if _auto_ep:
                _auto_pr = db.query(Project).filter(Project.id == _auto_ep.project_id).first()
                if _auto_pr and isinstance(_auto_pr.global_info, dict):
                    request.project_metadata = _auto_pr.global_info
                    logger.info("[analyze_scene] Automatically populated project_metadata from DB")
        except Exception as e:
            logger.warning(f"[analyze_scene] Failed to auto-fetch project_metadata: {e}")'''

if target in code:
    code = code.replace(target, replacement)
    with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print('Patched endpoints.py correctly.')
else:
    print('Target not found in endpoints.py.')
