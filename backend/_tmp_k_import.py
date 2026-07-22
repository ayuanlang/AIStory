# -*- coding: utf-8 -*-
from pathlib import Path
import ast

ai_path = Path(r"c:\AS\AIStory\backend\app\api\routers\workspace\shot_ai_generation.py")
text = ai_path.read_text(encoding="utf-8")
start = text.find("\ndef _import_scene_shot_rows_to_db(")
end = text.find('\n@router.post("/scenes/{scene_id}/apply_ai_result"')
if start < 0 or end < 0:
    raise SystemExit(f"markers {start} {end}")
body = text[start + 1 : end]

header = '''# -*- coding: utf-8 -*-
"""Import validated shot markdown rows into the Shot table."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.all_models import Entity, Episode, Project, Scene, Shot
from app.services.deletion_ops import _soft_delete_shots
from app.services.shot_markdown import (
    SHOT_MARKDOWN_COLUMN_WHITELIST,
    _dedupe_active_shot_records_for_display,
    _dedupe_shot_rows_for_import,
    _find_active_shot_by_business_id,
    _normalize_shot_business_id,
    _normalize_shot_markdown_col_key,
    _pick_shot_cell,
    _soft_delete_duplicate_active_shots_in_db,
)
from app.services.soft_delete import _active_shot_clause

logger = logging.getLogger("api_logger")

'''
svc = header + body
# Check if body uses now_bj_iso, flag_modified, json, etc.
extra_imports = []
if "now_bj_iso" in body:
    extra_imports.append("from app.core.time_utils import now_bj_iso")
if "flag_modified" in body:
    extra_imports.append("from sqlalchemy.orm.attributes import flag_modified")
if "json." in body or "json.loads" in body or "json.dumps" in body:
    extra_imports.append("import json")
if "_recompute" in body:
    extra_imports.append("# cost recompute via bind-era name — import if present")
# scan for _recompute
import re as _re
for m in _re.findall(r"\b(_[a-zA-Z][a-zA-Z0-9_]*)\b", body):
    pass

Path(r"c:\AS\AIStory\backend\app\services\shot_import_ops.py").write_text(svc, encoding="utf-8", newline="\n")

# Fix header with detected imports
src = Path(r"c:\AS\AIStory\backend\app\services\shot_import_ops.py").read_text(encoding="utf-8")
inject = []
if "now_bj_iso(" in body and "now_bj_iso" not in src.split("def ")[0]:
    inject.append("from app.core.time_utils import now_bj_iso\n")
if "flag_modified(" in body:
    inject.append("from sqlalchemy.orm.attributes import flag_modified\n")
if "json." in body:
    inject.append("import json\n")
if "_recompute_and_persist_project_cost_estimation" in body:
    inject.append("from app.services.project_cost_estimation import _recompute_and_persist_project_cost_estimation\n")
if inject:
    src = src.replace(
        "from app.services.soft_delete import _active_shot_clause\n\nlogger",
        "from app.services.soft_delete import _active_shot_clause\n" + "".join(inject) + "\nlogger",
        1,
    )
    Path(r"c:\AS\AIStory\backend\app\services\shot_import_ops.py").write_text(src, encoding="utf-8", newline="\n")

# Verify parse and missing names by compiling then importing carefully
ast.parse(src)
print("import ops lines", len(src.splitlines()))
# find undefined-looking names that are underscore helpers not imported
imported = set(_re.findall(r"import \((.*?)\)", src, _re.S))
# simpler: try import
import sys
sys.path.insert(0, r"c:\AS\AIStory\backend")
# Don't full import if media heavy - just check NameErrors by looking at body free names
# Replace in shot_ai_generation
imp = '''
# Shot import ops (canonical: app.services.shot_import_ops).
from app.services.shot_import_ops import (  # noqa: E402,F401
    _import_scene_shot_rows_to_db,
)

'''
new_ai = text[:start + 1] + imp + text[end:]
ai_path.write_text(new_ai, encoding="utf-8", newline="\n")
print("shot_ai lines", len(new_ai.splitlines()))
ast.parse(new_ai)
print("parse ok")
