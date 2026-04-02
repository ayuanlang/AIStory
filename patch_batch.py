import re

with open("backend/app/api/endpoints.py", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(
    r'def _run_scene_ai_shots_batch_item\(scene_id: int, episode_id: int, user_id: int\) -> Dict\[str, Any\]:',
    r'def _run_scene_ai_shots_batch_item(scene_id: int, episode_id: int, user_id: int, function_name: Optional[str] = None, system_api_id: Optional[int] = None) -> Dict[str, Any]:',
    text
)

text = re.sub(
    r'ai_generate_shots\(scene_id=scene_id, req=None, db=item_db, current_user=user_principal\),',
    r'ai_generate_shots(scene_id=scene_id, req=AIShotGenRequest(function_name=function_name, system_api_id=system_api_id), db=item_db, current_user=user_principal),',
    text
)

text = re.sub(
    r'active_future_map\[executor\.submit\(_run_scene_ai_shots_batch_item, sid, episode_id, user_id\)\] = sid',
    r'active_future_map[executor.submit(_run_scene_ai_shots_batch_item, sid, episode_id, user_id, function_name, system_api_id)] = sid',
    text
)

with open("backend/app/api/endpoints.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Patched")
