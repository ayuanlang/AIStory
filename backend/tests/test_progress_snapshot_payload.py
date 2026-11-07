from app.services.progress_snapshot_payload import slim_runtime_meta, slim_scene_unit


def test_slim_runtime_meta_drops_edit_draft_and_keeps_staging_flag():
    slim = slim_runtime_meta(
        {
            "scene_block": "【场景名称】办公室\n【建置】\n桌\n【入戏】\n坐下",
            "called_subskills": ["staging"],
            "current_step": "staging",
        },
        node_name="scene_subskill_scene",
        status="success",
    )
    assert "scene_block" not in slim
    assert slim["has_scene_block"] is True
    assert slim["has_staging_import_body"] is True
    assert slim["scene_name"] == "办公室"
    assert slim["current_step"] == "staging"
    assert "has_derived_env_signals" not in slim


def test_slim_runtime_meta_flags_derived_env_without_the_draft():
    slim = slim_runtime_meta(
        {"scene_block": "【本场衍生环境名】天台"},
        node_name="scene_subskill_scene",
        status="running",
    )
    assert slim["has_derived_env_signals"] is True
    assert "scene_block" not in slim


def test_slim_scene_unit_drops_markdown_body():
    slim = slim_scene_unit({
        "scene_id": "EP01_SC01",
        "scene_markdown": "【场景名称】高空\n正文",
        "import_status": "success",
    })
    assert "scene_markdown" not in slim
    assert slim["has_scene_markdown"] is True
    assert slim["scene_name"] == "高空"
    assert slim["import_status"] == "success"
