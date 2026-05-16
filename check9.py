import sys
sys.path.append('c:/AS/AIStory/backend')
import json
import re

f = open('c:/AS/AIStory/debug_append.txt', 'r', encoding='utf-8')
d = json.loads(f.read().split('================\n')[-4])

from app.api.endpoints import _append_video_api_ref_mapping

out = _append_video_api_ref_mapping(
    d['prompt'], 
    d['refs'], 
    d['ref_image_url'], 
    d['last_frame_url'], 
    entity_lookup=d['entity_lookup']
)
print('Total @Image:', out.count('@Image'))
