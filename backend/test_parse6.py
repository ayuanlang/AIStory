import json
import sys
sys.path.insert(0, './backend')
from app.services.generation_runtime.callbacks import _compact_generation_callback_payload

payload_str = '''{"eventData": {"status": "SUCCESS", "results": [{"url": "https://test.mp4", "name":"videoUrl"}]}}'''
payload = json.loads(payload_str)
print(json.dumps(_compact_generation_callback_payload(payload)))
print('GENERATION_CALLBACK_MAX_BYTES=', getattr(sys.modules['app.services.generation_runtime.callbacks'], 'GENERATION_CALLBACK_MAX_BYTES', 0))

