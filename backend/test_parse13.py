import json
import sys
sys.path.insert(0, './backend')
from app.services.generation_runtime.job_store import _extract_job_result_url

payload_str = '''{"eventData": {"taskId": "2082363026446901249", "status": "SUCCESS", "results": [{"url": "https://test.mp4", "name":"videoUrl"}]}}'''
payload = json.loads(payload_str)
print('extract URL:', _extract_job_result_url(payload))

