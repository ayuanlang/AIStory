import codecs
with codecs.open('backend/app/api/endpoints.py', 'r', 'utf-8') as f:
    text = f.read()

text = text.replace('or "scene_analysis_routed_base.txt"', 'or "skills/scene_analysis_feature_stack/scene_planning.md"')

with codecs.open('backend/app/api/endpoints.py', 'w', 'utf-8') as f:
    f.write(text)
