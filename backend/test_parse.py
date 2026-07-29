import json
import sys
sys.path.insert(0, './backend')
from app.services.generation_runtime.callbacks import _extract_callback_status, _extract_job_result_url, _normalize_generation_status

payload_str = '''{"eventData": {"status": "SUCCESS", "results": [{"url": "https://test.mp4"}]}}'''
payload = json.loads(payload_str)
print('raw:', _extract_callback_status(payload))
print('norm:', _normalize_generation_status(_extract_callback_status(payload)))
print('url:', _extract_job_result_url(payload))

