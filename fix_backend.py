import sys

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('if effective_scene_analysis_mode == "entity_design":', 'if effective_scene_analysis_mode in ["entity_design", "2_pass_generate_assets"]:', 100)

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
