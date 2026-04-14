import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from app.api.endpoints import EntityOut
class MockDBEntity:
    def __init__(self):
        self.id = 1
        self.image_url = None
        self.generation_prompt_en = None
        self.generation_prompt_cn = None
        self.anchor_description = None
        self.visual_dependencies = ''
        self.dependency_strategy = '{}'
        self.custom_attributes = '{"oss_uploaded_success": false}'

    # Missing optional fields:
        self.name = None
        self.type = None
        self.description = None
        self.name_en = None
        self.gender = None
        self.role = None
        self.archetype = None
        self.appearance_cn = None
        self.clothing = None
        self.action_characteristics = None
        self.atmosphere = None
        self.visual_params = None
        self.narrative_description = None
        
out = EntityOut.model_validate(MockDBEntity())
print("SUCCESS (model_validate):", out.custom_attributes)

# Since FastAPI passes an array:
from pydantic import TypeAdapter
from typing import List
ta = TypeAdapter(List[EntityOut])
out_list = ta.validate_python([MockDBEntity()])
print("SUCCESS (TypeAdapter):", out_list[0].custom_attributes)


