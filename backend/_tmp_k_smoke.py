import importlib, sys
from pathlib import Path
sys.path.insert(0, r"c:\AS\AIStory\backend")
for k in list(sys.modules):
    if k.startswith("app.api.routers.workspace") or "shot_list_compact" in k or "shot_ai" in k:
        sys.modules.pop(k, None)

try:
    import app.api.routers.workspace as wp
except Exception as e:
    print("IMPORT FAIL", type(e).__name__, e)
    raise

paths = {getattr(r, "path", None) for r in wp.router.routes}
for need in [
 "/episodes/{episode_id}/shots",
 "/scenes/{scene_id}/ai_generate_shots",
 "/episodes/{episode_id}/scenes/ai_shots/batch/start",
 "/scenes/{scene_id}/apply_ai_result",
 "/scenes/{scene_id}/shots",
 "/prompts/shot-generation/route-preview",
]:
    print("route", need, need in paths)

import app.api.routers.workspace.shot_ai_generation as sai
import app.api.routers.workspace.shots as shots
from app.services.shot_list_compact import _build_compact_shot_payload
assert sai.router is wp.router
assert shots._build_compact_shot_payload is _build_compact_shot_payload
assert callable(sai.ai_generate_shots)
print("sizes", len(Path(shots.__file__).read_text(encoding="utf-8").splitlines()),
      len(Path(sai.__file__).read_text(encoding="utf-8").splitlines()))
import app.main
print("main OK")
