# -*- coding: utf-8 -*-
"""Audit recently extracted services for call-site references + dead imports in thinned routers."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(r"c:\AS\AIStory\backend")
APP = ROOT / "app"

services = [
    "app.services.generation_job_pool",
    "app.services.shot_media_batch_status",
    "app.services.shot_media_batch_jobs",
    "app.services.scene_ai_shots_batch",
    "app.services.scene_markdown_runner",
    "app.services.scene_markdown_orchestration",
    "app.services.script_progress_helpers",
    "app.services.subject_index_resolve",
    "app.services.analyze_scene_subject_checks",
    "app.services.analyze_scene_text_ops",
    "app.services.analyze_scene_integrity",
    "app.services.shot_import_ops",
]

# Count import references across app/
all_py = list(APP.rglob("*.py"))
print("=== service import reference counts ===")
for mod in services:
    needle = mod
    short = mod.split(".")[-1]
    count = 0
    files = []
    for p in all_py:
        if p.name == f"{short}.py" and "services" in p.parts:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if needle in t or f"from app.services.{short} import" in t or f"import app.services.{short}" in t:
            count += 1
            files.append(str(p.relative_to(ROOT)))
    print(f"{short:40s} refs={count:2d}  {files[:5]}")

# Check job_pool / video_jobs / batch_media / analyze_scene / progress_flow for unused imports
targets = [
    ROOT / "app/api/routers/generation/job_pool.py",
    ROOT / "app/api/routers/generation/video_jobs.py",
    ROOT / "app/api/routers/generation/batch_media.py",
    ROOT / "app/api/routers/prompts/analyze_scene.py",
    ROOT / "app/api/routers/prompts/progress_flow.py",
    ROOT / "app/services/generation_job_pool.py",
    ROOT / "app/services/shot_media_batch_jobs.py",
    ROOT / "app/services/scene_markdown_runner.py",
]

print("\n=== unused imported names (AST) ===")
for path in targets:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(path.name, "PARSE FAIL", e)
        continue
    imported = {}  # name -> lineno
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name == "*":
                    continue
                imported[name] = node.lineno
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imported[name] = node.lineno
    # also names from multi-line imports mid-file (same as body ImportFrom)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
    # ignore common keepers
    keep = {"annotations", "router", "_shared"}
    unused = sorted(n for n in imported if n not in used and n not in keep)
    if unused:
        print(f"\n{path.relative_to(ROOT)} unused imports ({len(unused)}):")
        for n in unused[:40]:
            print(f"  L{imported[n]} {n}")
        if len(unused) > 40:
            print(f"  ... +{len(unused)-40} more")
    else:
        print(f"{path.relative_to(ROOT)}: no unused top-level imports")
