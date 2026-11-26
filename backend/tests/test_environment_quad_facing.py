# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.environment_quad_facing import quad_facing_lock


_SCRIPT = """
FOCAL_MM = 35
mass("地面", "floor", east=0, north=0, along_east=6.5, along_north=7.5, height=0.1, bottom=0)
mass("南墙墙皮", "wall", east=0, north=-3.6, along_east=6.5, along_north=0.2, height=2.9, bottom=0)
mass("北墙墙皮", "wall", east=0, north=3.6, along_east=6.5, along_north=0.2, height=2.9, bottom=0)
mass("书案", "furniture", east=0, north=0, along_east=1.8, along_north=0.8, height=0.75, bottom=0, face="上")
mass("库门", "door", east=0, north=-3.5, along_east=1.6, along_north=0.08, height=2.4, bottom=0, state="半开")
mass("监控屏", "furniture", east=3.1, north=0, along_east=0.08, along_north=1.6, height=0.9, bottom=1.2, face="西")
mass("顾沉舟", "person", east=0, north=-1, along_east=0.45, along_north=0.25, height=1.8, bottom=0)
"""


def _subject_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.startswith("[@"))


def test_facing_lock_uses_the_white_model_axes_and_skips_people():
    lock = quad_facing_lock("书斋", _SCRIPT)
    subjects = _subject_lines(lock)
    assert lock.startswith("【朝向锁】书斋")
    assert "长短边等朝向与白模不一致的，与白模保持一致" in lock
    assert "[@书案]：左上与左下用宽的一面。右上与右下用窄的一面。朝上。四格不写成朝着镜头。" in lock
    assert "左上这一格在镜头后，不点名" in lock
    assert "左下这一格在正面" in lock
    assert "半开，门板挡住洞口的一半" in lock
    assert "左上屏面朝画面左，见侧沿" in lock
    assert "右上屏面朝着镜头" in lock
    assert "左下屏面朝画面右，见侧沿" in lock
    assert "右下屏面背对镜头" in lock
    assert "顾沉舟" not in lock
    assert "米" not in subjects
    for word in ("东", "南", "西", "北"):
        assert word not in subjects


def test_north_south_long_edge_swaps_the_wide_cells():
    script = (
        'mass("卧榻", "furniture", east=0, north=0, along_east=0.9, along_north=2.1, '
        'height=0.5, bottom=0, face="上")'
    )
    lock = quad_facing_lock("卧房", script)
    assert "[@卧榻]：左上与左下用窄的一面。右上与右下用宽的一面。朝上。四格不写成朝着镜头。" in lock


def test_square_top_has_no_wide_sentence():
    script = 'mass("方几", "furniture", east=0, north=0, along_east=0.8, along_north=0.9, height=0.4, bottom=0, face="上")'
    lock = quad_facing_lock("茶室", script)
    assert "宽的一面" not in lock
    assert "窄的一面" not in lock
    assert "[@方几]：朝上。四格不写成朝着镜头。" in lock


def test_people_only_script_has_no_lock():
    script = 'mass("顾沉舟", "person", east=0, north=0, along_east=0.45, along_north=0.25, height=1.8, bottom=0)'
    assert quad_facing_lock("书斋", script) == ""
