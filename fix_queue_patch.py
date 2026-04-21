import os
import re

endpoints_path = r'c:\AS\AIStory\backend\app\api\endpoints.py'
with open(endpoints_path, 'r', encoding='utf-8') as f:
    endpoints_code = f.read()

endpoints_imports = '''import json
import os

QUEUE_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), " queue_config.json\)
def _load_queue_config():
 if os.path.exists(QUEUE_CONFIG_FILE):
 try:
 with open(QUEUE_CONFIG_FILE, \r\) as f:
 return json.load(f)
 except Exception:
 pass
 return {\queue_threads\: 20, \callback_threads\: 20}

_q_conf = _load_queue_config()
'''

endpoints_code = endpoints_code.replace(
 'GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY = max(1, int(os.getenv(\GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY\, \4\) or 4))',
 'GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY = max(1, int(_q_conf.get(\callback_threads\, 20)))'
)

gtq_path = r'c:\AS\AIStory\backend\app\services\generation_task_queue.py'
with open(gtq_path, 'r', encoding='utf-8') as f:
 gtq_code = f.read()

gtq_imports = '''import json
import os

QUEUE_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), \queue_config.json\)
def _load_queue_config():
 if os.path.exists(QUEUE_CONFIG_FILE):
 try:
 with open(QUEUE_CONFIG_FILE, \r\) as f:
 return json.load(f)
 except Exception:
 pass
 return {\queue_threads\: 20, \callback_threads\: 20}

_q_conf = _load_queue_config()
'''

gtq_code = gtq_code.replace(
 '_REQUESTED_WORKER_THREADS = max(1, int(os.getenv(\GENERATION_QUEUE_WORKER_THREADS\, str(_DEFAULT_WORKER_THREADS)) or _DEFAULT_WORKER_THREADS))',
 '_REQUESTED_WORKER_THREADS = max(1, int(_q_conf.get(\queue_threads\, 20)))'
)

# Uncap it if it's below 20
gtq_code = gtq_code.replace(
 '_WORKER_THREAD_CAP = max(1, _POOL_CAPACITY // 2)',
 '_WORKER_THREAD_CAP = max(20, _POOL_CAPACITY // 2)'
)

# Write back
with open(gtq_path, 'w', encoding='utf-8') as f:
 f.write(gtq_imports + gtq_code)

with open(endpoints_path, 'w', encoding='utf-8') as f:
 f.write(endpoints_imports + endpoints_code)

print(\Patched globals\)
