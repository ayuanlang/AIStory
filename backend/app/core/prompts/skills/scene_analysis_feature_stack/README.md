# Scene Analysis Feature Stack

Live prompt files for the script-analysis flow (`script_analysis_flow/registry.py`). Classic mode still uses `scene_analysis.txt`.

## Live node → prompt

| Node | Prompt | Notes |
| :--- | :--- | :--- |
| `scene_split` | `scene_planning_1_subskill_cut_transition.md` | 全局统筹；CHAR/PROP 抽取权威 |
| `environment_plan` | `scene_planning_1_subskill_environment.md` | |
| `scene_subskill_pipeline` | `scene_planning_1_subskill_drama_standardization.md` → `combat?` → `derived_framing` → `staging_env` | per-scene；武戏只注入 `combat.md` |
| `asset_design_character` | `entity_design_character.md` + inject `entity_design_common.md` | |
| `asset_design_prop` | `entity_design_prop.md` + inject `entity_design_common.md` | |
| `asset_design_environment` | `entity_design_environment_and_poster.md` + inject `entity_design_common.md` | |
| `storyboard_generation` | `skills/shot_generation.md` | |

## Kept but not a live node

| File | Why keep |
| :--- | :--- |
| `scene_planning_1_script_optimization.md` | 只读基线 / Parent；默认 `prompt_file` 与前端若干 `fetchPrompt` 仍引用 |
| `entity_design_common.md` | 资产设计注入共通段 |

## Retired (do not inject)

Moved to `_archive/2026-09-05-retired/`:

- `scene_planning_2_1_assets_extraction.md` — `assets_extraction` retired
- `scene_planning_2_2_beats_generation.md` — `scene_markdown` retired
- `scene_planning_1_subskill_vfx.md` / `scene_planning_1_subskill_xian_attack.md` — remap to `combat.md`

Older monoliths stay under `_archive/`.
