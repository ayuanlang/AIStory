# Prompt Chain Matrix

## Scope
This matrix defines the canonical data contract across:
- Global Story DNA
- Episode Story DNA
- Scene List JSON
- Episode Script Markdown
- Scene Analysis
- Shot Generation

Goal: keep `Episode -> Scene -> Shot` hierarchical continuity deterministic and machine-checkable.

## Canonical Hierarchical IDs
- Episode ID: `EPxx` (zero-padded)
- Scene ID: `EPxx_SCyy` (zero-padded, unique within episode)
- Shot ID: `EPxx_SCyy_SHzz` (zero-padded, unique within scene)

## Stage-by-Stage Contract

| Stage | Required Output Keys/Labels | Downstream Consumer | Mapping Notes |
| :--- | :--- | :--- | :--- |
| `story_generator_global.txt` | `EPxx` in episode plan lines | Episode Outline | Global only sets canonical episode coding policy and venue/continuity seeds. |
| `story_generator_episode.txt` | `episode_id`, `scene_id`, `Entry State -> Exit State`, `Environment Seed` | Scene List + Episode Script | `entry_state` ↔ `Entry State`; `exit_state` ↔ `Exit State`; `Environment Seed` routes into `Environment Relation` decisions downstream. |
| `script_generator_scenes.txt` | `episode_id`, `scene_id`, `scene_no`, `environment_relation`, `entry_state`, `exit_state` | Scene Analysis + DB scene records | `environment_relation` values: `NEW`, `REUSE:<EnvName>`, `VARIANT_OF:<EnvName>`. |
| `script_generator_episode_script.txt` | `Scene ID`, `Environment Relation`, `Entry State`, `Exit State`, beat-level structure | Scene Analysis + Shot Generation | Markdown label form mirrors snake_case JSON form from scene list stage. |
| `scene_analysis.txt` | `Episode ID`, `Scene ID`, `Environment Relation`, `Entry State`, `Exit State` + validation checks | Shot Generation + entity extraction | Includes mandatory continuity checks and state-handoff verification. |
| `shot_generator.txt` | `Scene ID`, `Shot ID` | Final shot table | Requires `Shot ID` prefix to exactly match row `Scene ID` (`EPxx_SCyy`). |

## Label Mapping (Authoritative)

| JSON/Snake Case | Markdown/Display Label | Meaning |
| :--- | :--- | :--- |
| `episode_id` | `Episode ID` | Canonical episode key |
| `scene_id` | `Scene ID` | Canonical scene key |
| `environment_relation` | `Environment Relation` | Reuse/new/variant decision |
| `entry_state` | `Entry State` | Start snapshot for continuity |
| `exit_state` | `Exit State` | End snapshot for continuity |

## Environment Relation Decision Rule
- `NEW`: first creation of a scene environment variant.
- `REUSE:<EnvName>`: exact reuse (structure/view/light/background set unchanged).
- `VARIANT_OF:<EnvName>`: same venue family but required split due to axis/view/background/light/significant composition change.

## Beat-Level Minimum (Scene-Side)
- Beats must be time-ordered and action-causal.
- Beats must be spatially activated in scene space (no vacuum performance).
- Beats should use explicit entity references in `[]` where required by prompt rules.
- Include enhancement constraints when instructed (e.g.,角色高光, 视觉转场).
- Beat sequence must support stable start/end states for shot decomposition.

## Validation Checklist (Cross-Stage)
- IDs are canonical and zero-padded (`EPxx`, `EPxx_SCyy`, `EPxx_SCyy_SHzz`).
- One-to-many hierarchy holds (`Episode -> Scenes -> Shots`).
- `Scene ID` prefix matches `Episode ID`.
- `Shot ID` prefix matches `Scene ID`.
- `Environment Relation` is present and valid in scene-bearing stages.
- `Entry State` / `Exit State` are present and logically hand off between adjacent scenes.
- Axis/background/view changes trigger `VARIANT_OF` rather than silent reuse.

## Maintenance Rule
When any key/label/ID format changes in one prompt, update all affected prompts and this matrix in the same change.
