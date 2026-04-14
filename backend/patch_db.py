import re

with open("app/models/all_models.py", "r", encoding="utf-8") as f:
    text = f.read()

pattern = r"ai_scene_analysis_result\s*=\s*Column\(Text,\s*nullable=True\)"
replacement = "ai_scene_analysis_result = Column(Text, nullable=True)\n    ai_entity_design_result = Column(Text, nullable=True)"

replaced = re.sub(pattern, replacement, text)

with open("app/models/all_models.py", "w", encoding="utf-8") as f:
    f.write(replaced)

# Now patch app/api/endpoints.py Schema
with open("app/api/endpoints.py", "r", encoding="utf-8") as f:
    text = f.read()

p1 = r"ai_scene_analysis_result:\s*Optional\[str\]\s*=\s*None"
r1 = "ai_scene_analysis_result: Optional[str] = None\n    ai_entity_design_result: Optional[str] = None"

text = re.sub(p1, r1, text)

with open("app/api/endpoints.py", "w", encoding="utf-8") as f:
    f.write(text)

print("DB fields added!")
