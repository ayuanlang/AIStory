import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app.api.endpoints import EntityOut
from fastapi.routing import serialize_response
from typing import List
import pydantic, asyncio

class MockDBEntity:
    id = 1
    image_url = None
    generation_prompt_en = None
    generation_prompt_cn = None
    anchor_description = None
    visual_dependencies = ''
    dependency_strategy = '{}'
    custom_attributes = '{"a": 1}'

async def test():
    from pydantic.fields import FieldInfo
    try:
        res = await serialize_response(
            field=FieldInfo(annotation=List[EntityOut]),
            response_content=[MockDBEntity()]
        )
        print('SUCCESS', res)
    except Exception as e:
        print('FAILED', e)
        import traceback
        traceback.print_exc()

asyncio.run(test())
