# -*- coding: utf-8 -*-
from app.services.story_episode_coverage import (
    missing_episode_numbers,
    splice_episode_blocks,
)


def test_splice_fills_gap_and_drops_unclosed_tail():
    base = """[STORY_DNA_OUTPUT_START]
## 9) 分集规划
[EPISODE_BLOCK_START:EP01]
- EP01 标题
[EPISODE_BLOCK_END:EP01]
[EPISODE_BLOCK_START:EP03]
半截没有收束
### Episode Coverage Audit
Planned:3
[STORY_DNA_OUTPUT_END]
"""
    addition = """
[EPISODE_BLOCK_START:EP02]
- EP02 正文
[EPISODE_BLOCK_END:EP02]
[EPISODE_BLOCK_START:EP03]
- EP03 正文
[EPISODE_BLOCK_END:EP03]
"""
    merged = splice_episode_blocks(base, addition)
    assert missing_episode_numbers(merged, 3) == []
    assert "半截没有收束" not in merged
    assert merged.index("EP02") < merged.index("EP03")
    assert merged.index("[EPISODE_BLOCK_END:EP03]") < merged.index("Episode Coverage Audit")
    assert "[STORY_DNA_OUTPUT_END]" in merged


def test_missing_ignores_summary_without_block_markers():
    text = """
[EPISODE_BLOCK_START:EP01]
- EP01
[EPISODE_BLOCK_END:EP01]
EP02–EP04 同上，略。
"""
    assert missing_episode_numbers(text, 4) == [2, 3, 4]
