import json
import sys
sys.path.insert(0, './backend')
from app.services.generation_runtime.job_store import _compact_job_result, _extract_job_result_url

event_data = {"taskId": "123", "status": "SUCCESS", "results": [{"url": "https://test.mp4", "name":"videoUrl"}]}
compacted = _compact_job_result(event_data)
print('compacted:', compacted)
print('url:', _extract_job_result_url(compacted))

