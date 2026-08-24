# -*- coding: utf-8 -*-
from app.services.analyze_scene_subject_checks import _detect_subject_index_coverage_warnings


INDEX_WITH_COVER = """
| subject_no | subject_type | subject_name_zh | subject_name_en |
|---|---|---|---|
| S001 | character | 蒙治 | Meng Zhi |
| S010 | environment | 秦朝宫殿 | Qin Palace |
| S018 | cover_poster | 封面海报 | Project Cover Poster |
"""


def test_poster_only_payload_does_not_crash_coverage_check():
    meta = _detect_subject_index_coverage_warnings(
        INDEX_WITH_COVER,
        {
            "environments": [],
            "posters": [
                {
                    "subject_no": "S018",
                    "name": "封面海报",
                    "name_en": "Project Cover Poster",
                }
            ],
        },
    )
    assert meta["missing_by_bucket"]["covers"] == []
    assert meta["missing_by_bucket"]["posters"] == []
    assert "封面海报" not in (meta.get("warnings") or [])


def test_cover_bucket_payload_also_covers_index_poster_row():
    meta = _detect_subject_index_coverage_warnings(
        INDEX_WITH_COVER,
        {
            "covers": [
                {
                    "subject_no": "S018",
                    "name": "封面海报",
                    "name_en": "Project Cover Poster",
                }
            ],
        },
    )
    assert meta["missing_total"] >= 1  # environment still missing
    assert meta["missing_by_bucket"]["covers"] == []
    assert meta["missing_by_bucket"]["posters"] == []
