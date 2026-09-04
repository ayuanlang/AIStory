# Retired 2026-09-05

这些文件不再注入活节点。保留仅供对照，禁止当运行时权威。

| 文件 | 原节点 | 退役原因 | 现权威 |
| :--- | :--- | :--- | :--- |
| `scene_planning_2_1_assets_extraction.md` | `assets_extraction` | 节点 `enabled=False` / `status=retired`。CHAR/PROP 不再走 LLM 整集抽取。 | `scene_split` → `scene_planning_1_subskill_cut_transition.md` 的 `[CHAR_EXTRACT]` / `[PROP_EXTRACT]` |
| `scene_planning_2_2_beats_generation.md` | `scene_markdown` | 节点 `enabled=False` / `status=retired`。场景表由 staging 成稿程序提取。 | `scene_subskill_pipeline` → `scene_planning_1_subskill_staging_env.md` |
| `scene_planning_1_subskill_vfx.md` | 无独立节点 | `prompt_resolve` / pipeline 一律 remap 到武戏，从不注入本文件。 | `scene_planning_1_subskill_combat.md` |
| `scene_planning_1_subskill_xian_attack.md` | 无独立节点 | 同上。 | `scene_planning_1_subskill_combat.md` |

旧路径请求（`skills/scene_analysis_feature_stack/scene_planning_1_subskill_vfx.md` 等）仍由 `prompt_resolve.py` 按文件名 remap 到 `combat.md`，不读本目录。
