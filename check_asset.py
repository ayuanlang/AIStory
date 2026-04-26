import json
import sys

def check():
    with open('app/api/endpoints.py', 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')
        for i, line in enumerate(lines):
            if 'async def _run_generate_image(' in line or 'def _bind_generated_media_to' in line:
                for idx in range(i, i+300):
                    if idx < len(lines):
                        if 'Asset(' in lines[idx] or '_register_generated_asset' in lines[idx]:
                            print(f"endpoints.py:{idx+1}: {lines[idx]}")
                    
check()
