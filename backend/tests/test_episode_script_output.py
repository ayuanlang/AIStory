# -*- coding: utf-8 -*-
from app.services.episode_script_output import (
    extract_official_episode_script,
    is_acceptable_episode_script_markdown,
)
from app.services.markdown_generation import _parse_episode_heading_from_markdown


OFFICIAL_BODY = """# 1-工牌错位
## 核心重点
- **卖点**：卖点1｜名=身份错位｜类型=悬疑质感｜主承载场=EP01_SC01
- **重要情节**：误刷工牌后必须在审计前保住解雇信。
- **重要情绪**：错位压迫｜场=EP01_SC01｜高潮=门开见信｜核心情绪点=身份错位
- **契科夫的枪**：G01｜锚=工牌+解雇信墨线｜本集=埋@EP01_SC01@Beat 1
## 场景列表
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[ENV_BLOCK_START]
星澜电梯间
[ENV_BLOCK_END]
[BEAT_STREAM_START]
[BEAT_START:1]
- Beat 1：林一刷卡进电梯。
[BEAT_END:1]
[BEAT_STREAM_END]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
## 剧情一句话与交接
林一仍握着工牌，解雇信照片在手机里。
## 结尾钩子
保安按响门铃。
[EMERGENCY_RECOVERY_BLOCK_START]
适用=有下集
#项1：紧急待核销=工牌未交；未决态=审计倒计时；下集须兑现=开场前段；依据=结尾钩子；状态=待下集核销
#集级：待核销项数=1｜自检=通过
[EMERGENCY_RECOVERY_BLOCK_END]
"""


def test_extract_official_from_output_markers():
    full = (
        "[EPISODE_SCRIPT_THINKING_START]\n"
        "## -1) 类型执行摘要\n分析过程很长，不应出现在剧本页。\n"
        "[EPISODE_SCRIPT_THINKING_END]\n"
        f"[EPISODE_SCRIPT_OUTPUT_START]\n{OFFICIAL_BODY}[EPISODE_SCRIPT_OUTPUT_END]\n"
    )
    official = extract_official_episode_script(full)
    assert official.startswith("# 1-工牌错位")
    assert "核心重点" in official
    assert "契科夫的枪" in official
    assert "分析过程很长" not in official
    assert "[EMERGENCY_RECOVERY_BLOCK_START]" in official
    assert is_acceptable_episode_script_markdown(full)


def test_extract_official_strips_legacy_analysis():
    legacy = (
        "# 1-工牌错位\n"
        "## -1) 类型执行摘要\n"
        "上下集逻辑核验=已完成\n"
        "大纲逐字分析台账=很长\n"
        "## 场景列表\n"
        "[SCENES_BLOCK_START]\nscene\n[SCENES_BLOCK_END]\n"
        "## 剧情连贯自检\n核销总表=通过\n"
        "## 剧情一句话与交接\n林一仍握着工牌。\n"
        "## 结尾钩子\n保安上门。\n"
    )
    official = extract_official_episode_script(legacy)
    assert official.startswith("# 1-工牌错位")
    assert "类型执行摘要" not in official
    assert "剧情连贯自检" not in official
    assert "[SCENES_BLOCK_START]" in official
    assert "剧情一句话" in official
    assert "结尾钩子" in official


def test_extract_official_trims_process_analysis_from_output():
    messy = (
        "[EPISODE_SCRIPT_OUTPUT_START]\n"
        "# 1-工牌错位\n"
        "## 核心重点\n"
        "- **卖点**：身份错位\n"
        "- **重要情节**：误刷工牌\n"
        "- **重要情绪**：错位压迫\n"
        "- **契科夫的枪**：G01｜工牌\n"
        "## 娱乐化段子\n"
        "类型=自嘲｜落点=EP01_SC01@Beat 3｜一句=这牌比我先当上高管\n"
        "## 分集开局规划\n"
        "#多单线:结论=双线｜不应进剧本页\n"
        "## 场景列表\n"
        "[SCENES_BLOCK_START]\n"
        "[SCENE_START:EP01_SC01]\n"
        "[ENV_BLOCK_START]\n星澜电梯间\n[ENV_BLOCK_END]\n"
        "[BEAT_STREAM_START]\n[BEAT_START:1]\n- Beat 1：林一刷卡。\n[BEAT_END:1]\n"
        "[BEAT_STREAM_END]\n[SCENE_END:EP01_SC01]\n[SCENES_BLOCK_END]\n"
        "## 剧情一句话与交接\n林一仍握着工牌。\n"
        "## 结尾钩子\n保安上门。\n"
        "[EMERGENCY_RECOVERY_BLOCK_START]\n适用=有下集\n"
        "#项1：紧急待核销=工牌未交；状态=待下集核销\n"
        "#集级：待核销项数=1｜自检=通过\n"
        "[EMERGENCY_RECOVERY_BLOCK_END]\n"
        "## 桥段凝聚汇总\n母题=身份错位\n"
        "━━━━━━━━\n"
        "[BRIDGE_BLOCK_START]\n母题=身份错位｜回收=本集弧线收束\n[BRIDGE_BLOCK_END]\n"
        "━━━━━━━━\n"
        "[EPISODE_SCRIPT_OUTPUT_END]\n"
    )
    official = extract_official_episode_script(messy)
    assert "核心重点" in official
    assert "契科夫的枪" in official
    assert "[SCENES_BLOCK_START]" in official
    assert "- Beat 1：林一刷卡。" in official
    assert "[EMERGENCY_RECOVERY_BLOCK_START]" in official
    assert "剧情一句话" in official
    assert "结尾钩子" in official
    assert "娱乐化段子" not in official
    assert "分集开局规划" not in official
    assert "桥段凝聚汇总" not in official
    assert "BRIDGE_BLOCK" not in official
    assert "这牌比我先当上高管" not in official


def test_heading_parse_reads_inside_output_markers():
    full = (
        "[EPISODE_SCRIPT_THINKING_START]\n摘要\n[EPISODE_SCRIPT_THINKING_END]\n"
        "[EPISODE_SCRIPT_OUTPUT_START]\n# 2-夜审\n## 核心内容纲要\n一句\n"
        "[SCENES_BLOCK_START]\n[SCENES_BLOCK_END]\n[EPISODE_SCRIPT_OUTPUT_END]"
    )
    parsed = _parse_episode_heading_from_markdown(full)
    assert parsed.get("episode_number") == 2
    assert parsed.get("episode_title") == "夜审"
