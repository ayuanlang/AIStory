from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    visual_dependencies: Optional[List[str]] = []

class DBEntity:
    def __init__(self, id, deps):
        self.id = id
        self.visual_dependencies = deps

try:
    db_obj = DBEntity(1, '["abc", "def"]')
    obj = EntityOut.model_validate(db_obj)
    print("Test 3 Result:", getattr(obj, "visual_dependencies"))
except Exception as e:
    print("Test 3 Error:", e)

    