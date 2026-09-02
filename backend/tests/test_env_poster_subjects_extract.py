# -*- coding: utf-8 -*-
from app.services.analyze_scene_subject_checks import _reconcile_subjects_json_with_subject_index
from app.services.scene_subject_helpers import _extract_subjects_json_from_text


ENV_POSTER_JSON = """
{
  "environments": [
    {
      "subject_no": "EP01_SC01_ENV",
      "name": "龙门风月客栈内部",
      "name_en": "Dragon Gate Inn Interior",
      "generation_prompt_cn": "四向拼图基准。forbid \\\\."
    }
  ],
  "posters": [
    {
      "subject_no": "EP01_SC01_POSTER",
      "name": "封面海报",
      "name_en": "Cover Poster",
      "generation_prompt_cn": "电影级写实封面海报，固定 4:3 poster canvas。"
    }
  ]
}
"""


def test_extract_keeps_posters_alongside_environments():
    payload = _extract_subjects_json_from_text(ENV_POSTER_JSON)
    assert len(payload.get("environments") or []) == 1
    assert payload["environments"][0]["name"] == "龙门风月客栈内部"
    posters = (payload.get("posters") or []) + (payload.get("covers") or [])
    assert any(item.get("name") == "封面海报" for item in posters)


def test_reconcile_without_index_keeps_designed_cover_poster():
    extracted = _extract_subjects_json_from_text(ENV_POSTER_JSON)
    result = _reconcile_subjects_json_with_subject_index("", extracted)
    payload = result.get("subjects_json") or {}
    posters = (payload.get("posters") or []) + (payload.get("covers") or [])
    assert any(item.get("name") == "封面海报" for item in posters)
    assert len(payload.get("environments") or []) == 1


def test_extract_recovers_environment_when_prompt_has_raw_newlines():
    raw = """
{
  "environments": [
    {
      "subject_no": "S001",
      "name": "豪华游艇甲板",
      "name_en": "Luxury Yacht Deck",
      "generation_prompt_cn": "四向拼图基准。
开篇拓扑：甲板沿0度。
【四面内容基准】后景正对海平线。"
    }
  ],
  "posters": [
    {
      "name": "封面海报",
      "generation_prompt_cn": "电影级写实封面海报"
    }
  ]
}
"""
    payload = _extract_subjects_json_from_text(raw)
    names = [item.get("name") for item in (payload.get("environments") or [])]
    assert "豪华游艇甲板" in names
    assert any(
        item.get("name") == "封面海报"
        for item in (payload.get("posters") or []) + (payload.get("covers") or [])
    )


def test_extract_recovers_environments_when_prompt_has_unescaped_quotes():
    raw = """
{
  "environments": [
    {
      "subject_no": "S001",
      "name": "豪华游艇甲板",
      "name_en": "Luxury Yacht Deck",
      "generation_prompt_cn": "可见面="正面"，四向拼图基准。",
      "generation_prompt_en": "",
      "negative_prompt_en": "people"
    },
    {
      "subject_no": "S002",
      "name": "海面",
      "name_en": "Open Sea",
      "generation_prompt_cn": "开阔海面空镜，四面只写水天。",
      "generation_prompt_en": "",
      "negative_prompt_en": "people"
    }
  ],
  "posters": [
    {
      "name": "封面海报",
      "generation_prompt_cn": "电影级写实封面海报"
    }
  ]
}
"""
    payload = _extract_subjects_json_from_text(raw)
    names = [item.get("name") for item in (payload.get("environments") or [])]
    assert "豪华游艇甲板" in names
    assert "海面" in names
    deck = next(item for item in payload["environments"] if item["name"] == "豪华游艇甲板")
    assert "四向拼图基准" in str(deck.get("generation_prompt_cn") or "")
