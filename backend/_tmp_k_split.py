# -*- coding: utf-8 -*-
from pathlib import Path
import ast

shots_path = Path(r"c:\AS\AIStory\backend\app\api\routers\workspace\shots.py")
text = shots_path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

# 1) compact helpers -> service (lines 22-120 approx: constants + two defs before first router)
# Find markers
compact_const_start = text.find("_SHOT_LIST_COMPACT_TECH_KEYS = (")
compact_end = text.find('\n@router.get("/episodes/{episode_id}/shots"')
if compact_const_start < 0 or compact_end < 0:
    raise SystemExit(f"compact markers {compact_const_start} {compact_end}")
# include from const through build_compact (before router)
# go back to line start for const
compact_body = text[compact_const_start:compact_end]

compact_header = '''# -*- coding: utf-8 -*-
"""Compact shot-list payload helpers for episode shot listings."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

'''
# Does compact body need more imports? Read quickly via parse after writing - may need json already.
# Check body for names used
compact_src = compact_header + compact_body
# body may reference logger? check
if "logger." in compact_body:
    compact_src = compact_header.replace(
        "from typing import Any, Dict, Optional, Tuple\n",
        "import logging\nfrom typing import Any, Dict, Optional, Tuple\n\nlogger = logging.getLogger(\"api_logger\")\n",
    ) + compact_body

Path(r"c:\AS\AIStory\backend\app\services\shot_list_compact.py").write_text(compact_src, encoding="utf-8", newline="\n")

def export_names(src: str):
    tree = ast.parse(src)
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id != "logger":
                    names.append(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id != "logger":
                names.append(node.target.id)
    seen=set(); out=[]
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out

c_names = export_names(compact_src)
print("compact", c_names)

# 2) AI section from AIShotGenRequest to before read_shots
ai_start = text.find("\nclass AIShotGenRequest(")
ai_end = text.find('\n@router.get("/scenes/{scene_id}/shots"')
if ai_start < 0 or ai_end < 0:
    raise SystemExit(f"ai markers {ai_start} {ai_end}")
ai_body = text[ai_start + 1 : ai_end]

ai_header = '''# -*- coding: utf-8 -*-
"""Shot AI generation / batch / apply workspace section routes."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)

'''
ai_path = Path(r"c:\AS\AIStory\backend\app\api\routers\workspace\shot_ai_generation.py")
ai_path.write_text(ai_header + ai_body, encoding="utf-8", newline="\n")
print("shot_ai_generation lines", len((ai_header + ai_body).splitlines()))

# Rebuild shots: replace compact with import; remove AI block
imp_c = ["\n# Compact shot list helpers (canonical: app.services.shot_list_compact).\n",
         "from app.services.shot_list_compact import (  # noqa: E402,F401\n"]
for n in c_names:
    imp_c.append(f"    {n},\n")
imp_c.append(")\n")

new_text = text[:compact_const_start] + "".join(imp_c) + text[compact_end:ai_start + 1] + text[ai_end:]
shots_path.write_text(new_text, encoding="utf-8", newline="\n")
print("shots lines", len(new_text.splitlines()))

# Update __init__ - import shot_ai AFTER shots so shots CRUD registers first; order mostly for publish
init = Path(r"c:\AS\AIStory\backend\app\api\routers\workspace\__init__.py")
it = init.read_text(encoding="utf-8")
if "shot_ai_generation" not in it:
    it = it.replace(
        "from app.api.routers.workspace import shots as _shots  # noqa: F401,E402\n",
        "from app.api.routers.workspace import shots as _shots  # noqa: F401,E402\n"
        "from app.api.routers.workspace import shot_ai_generation as _shot_ai_generation  # noqa: F401,E402\n",
    )
    it = it.replace(
        "_SECTION_MODULES = (_episodes, _scenes, _shots, _admin_residual, _story_generator, _project_sharing, _episode_script_generator)",
        "_SECTION_MODULES = (_episodes, _scenes, _shots, _shot_ai_generation, _admin_residual, _story_generator, _project_sharing, _episode_script_generator)",
    )
    init.write_text(it, encoding="utf-8", newline="\n")
    print("init updated")

for p in [
    r"c:\AS\AIStory\backend\app\services\shot_list_compact.py",
    str(ai_path),
    str(shots_path),
]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print("parse ok", Path(p).name)
