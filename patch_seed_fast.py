import json
import os

with open('backend/app/data/system_api_seed.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    
# Avoid duplicates
if not any(item['model'] == 'sparkvideo-2.0-fast' for item in data['items']):
    data['items'].append({
          "name": "RunningHub SparkVideo 2.0 Fast (I2V)",
          "category": "Video",
          "provider": "runninghub",
          "base_url": "https://www.runninghub.cn",
          "model": "sparkvideo-2.0-fast",
          "modality": "video",
          "config": {
            "endpoint": "/openapi/v2/rhart-video/sparkvideo-2.0-fast/image-to-video",
            "query_endpoint": "/openapi/v2/query"
          },
          "deprecated": False,
          "is_active": True,
          "tags": ["runninghub", "i2v", "fast"]
    })
    data['count'] = len(data['items'])
    with open('backend/app/data/system_api_seed.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print('Updated system_api_seed.json')
else:
    print('Already in seed.json')
