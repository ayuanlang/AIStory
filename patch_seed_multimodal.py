import json
import os

with open('backend/app/data/system_api_seed.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    
if not any(item['model'] == 'sparkvideo-2.0-fast-multimodal' for item in data['items']):
    data['items'].append({
          "name": "RunningHub SparkVideo 2.0 Fast Multimodal",
          "category": "Video",
          "provider": "runninghub",
          "base_url": "https://www.runninghub.cn",
          "model": "sparkvideo-2.0-fast-multimodal",
          "modality": "video",
          "config": {
            "endpoint": "/openapi/v2/rhart-video/sparkvideo-2.0-fast/multimodal-video",
            "query_endpoint": "/openapi/v2/query"
          },
          "deprecated": False,
          "is_active": True,
          "tags": ["runninghub", "multimodal", "fast"]
    })
    data['count'] = len(data['items'])
    with open('backend/app/data/system_api_seed.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print('Updated system_api_seed.json')
else:
    print('Already in seed.json')
