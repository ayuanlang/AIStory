import json
import sys
sys.path.insert(0, './backend')
from app.services.generation_runtime.callbacks import _extract_job_result_url, _extract_callback_task_id, _compact_generation_callback_payload, _extract_callback_status, _normalize_generation_status

payload_str = '''{"eventData": {"taskId": "2082363026446901249", "status": "SUCCESS", "results": [{"url": "https://test.mp4", "name":"videoUrl"}]}}'''
payload = json.loads(payload_str)
print('callback extract url:', _extract_job_result_url(payload))
print('callback extract task_id:', _extract_callback_task_id(payload))
print('callback extract status raw:', _extract_callback_status(payload))
print('callback extract status norm:', _normalize_generation_status(_extract_callback_status(payload)))

