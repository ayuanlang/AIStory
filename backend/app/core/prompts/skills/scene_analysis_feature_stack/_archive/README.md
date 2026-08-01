# Archived obsolete prompts

These files conflict with the split production path and must **not** be injected at runtime.

| File | Replaced by |
| :--- | :--- |
| `scene_planning.md` | `scene_planning_1_script_optimization.md` + `scene_planning_2_1_assets_extraction.md` + `scene_planning_2_2_beats_generation.md` |
| `entity_design.md` | `entity_design_common.md` + character / prop / environment_and_poster |
| `entity_design_environment.md` | `entity_design_environment_and_poster.md` |

One-off patch scripts under `frontend/` / repo root that still mention these names are historical; live `ScriptEditor.jsx` and `script_analysis_flow/registry.py` already point to the split files.