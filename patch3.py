import re

with open('C:/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Change the base prompt to scene_planning.md
text = text.replace(
    'prompt_filename = request.prompt_file or "scene_analysis.txt"',
    'prompt_filename = request.prompt_file or "skill:scene_analysis_feature_stack/scene_planning.md"'
)

# 2. Add the two-step logic logic comment for now. 
print("File prepared.")
