import os
import re

fpath = r'c:\AS\AIStory\backend\app\api\endpoints.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update _register_asset_helper
content = content.replace(
    '["provider", "model", "duration", "width", "height", "aspect_ratio", "submit_aspect_ratio", "prompt", "seed"]',
    '["provider", "model", "duration", "width", "height", "aspect_ratio", "submit_aspect_ratio", "prompt", "seed", "idempotency_key"]'
)

# 2. Update _finalize_image_job_result_persistence
content = content.replace(
    '        finalized_result = dict(result)\n        if normalized_url:',
    '        if normalized_meta is None:\n            normalized_meta = {}\n        normalized_meta["idempotency_key"] = job_id\n\n        finalized_result = dict(result)\n        if normalized_url:'
)

# 3. Update _run_generate_image
content = content.replace(
    '        smart_meta = result_meta.get("smart_routing") if isinstance(result_meta.get("smart_routing"), dict) else {}',
    '        if job_id:\n            result_meta["idempotency_key"] = job_id\n            if isinstance(result, dict):\n                result["metadata"] = result_meta\n\n        smart_meta = result_meta.get("smart_routing") if isinstance(result_meta.get("smart_routing"), dict) else {}'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
