import codecs
with codecs.open('backend/app/core/prompts/scene_analysis_feature_skills.py', 'r', 'utf-8') as f:
    text = f.read()

text = text.replace('_DEFAULT_ROUTED_BASE_PROMPT = "scene_analysis_routed_base.txt"', '_DEFAULT_ROUTED_BASE_PROMPT = "skills/scene_analysis_feature_stack/scene_planning.md"')

with codecs.open('backend/app/core/prompts/scene_analysis_feature_skills.py', 'w', 'utf-8') as f:
    f.write(text)
