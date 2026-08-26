# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.cover_poster_brief import build_cover_poster_brief


def test_cover_poster_brief_uses_char_env_and_backfill():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=林岳｜名称_en=Lin
定位=男主
[CHAR_EXTRACT_END]
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“大堂”
定位=夜内对峙大厅
目标=本场空镜须=建立压迫｜服务=无｜可见落点=大门
情绪表达=主情绪=压迫｜空镜表达=灯下空堂
[SCENE_ENV_IDENT_END:EP01_SC01]
[SCENES_BLOCK_END]

### 第三部分：Project Visual Backfill
```json
{"project_visual_backfill":{"Global_Style":"写实古装","tone":"冷峻","lighting":"油灯暖点"}}
```
"""
    brief = build_cover_poster_brief(script)
    assert "[封面海报简报开始]" in brief
    assert "林岳" in brief
    assert "客栈大堂" in brief
    assert "压迫" in brief
    assert "写实古装" in brief


def test_cover_poster_brief_empty_without_sources():
    assert build_cover_poster_brief("") == ""
    assert build_cover_poster_brief("只是一段没有提取块的正文") == ""
