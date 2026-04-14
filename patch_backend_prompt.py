import codecs
import re

with codecs.open('backend/app/api/endpoints.py', 'r', 'utf-8') as f:
    text = f.read()

text = text.replace('request.prompt_file or "scene_analysis.txt"', 'request.prompt_file or "skills/scene_analysis_feature_stack/scene_planning.md"')

with codecs.open('backend/app/api/endpoints.py', 'w', 'utf-8') as f:
    f.write(text)

print('Patched backend endpoints.py')
