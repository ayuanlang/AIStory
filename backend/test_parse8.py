import json
import sys
sys.path.insert(0, './backend')
from app.services.generation_runtime.callbacks import _extract_job_result_url, _extract_callback_task_id, _compact_generation_callback_payload
from app.services.generation_runtime.job_store import _compact_job_result

payload_str = '''{"eventData": {"taskId": "123", "status": "SUCCESS", "results": [{"url": "https://test.mp4", "name":"videoUrl"}]}}'''
payload = json.loads(payload_str)
print('callback extract url:', _extract_job_result_url(payload))
print('callback extract task_id:', _extract_callback_task_id(payload))
print('compact job result url:', _extract_job_result_url(_compact_job_result(payload)))

