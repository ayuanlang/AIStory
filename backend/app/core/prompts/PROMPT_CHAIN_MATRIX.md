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
| `script_generator_scenes.txt` | `episode_id`, `scene_id`, `scene_no`, `environment_relation`, `observer_view`, `entry_state`, `exit_state` | Scene Analysis + DB scene records | `environment_relation` values: `NEW`, `REUSE:<EnvName>`, `VARIANT_OF:<EnvName>`. |
| `script_generator_episode_script.txt` | `Scene ID`, `Environment Relation`, `Base Environment Reference`, `Environment Delta`, `Observer View`, `Entry State`, `Exit State`, beat-level structure | Scene Analysis + Shot Generation | Markdown label form mirrors snake_case JSON form from scene list stage. |
| `scene_analysis.txt` | `Episode ID`, `Scene ID`, `Environment Relation`, `Base Environment Reference`, `Environment Delta`, `Observer View`, `Entry State`, `Exit State` + validation checks | Shot Generation + entity extraction | Includes mandatory continuity checks, base-delta inheritance checks, observer-POV checks, and state-handoff verification. |
| `shot_generator.txt` | `Scene ID`, `Shot ID` | Final shot table | Requires `Shot ID` prefix to exactly match row `Scene ID` (`EPxx_SCyy`). |

## Label Mapping (Authoritative)

| JSON/Snake Case | Markdown/Display Label | Meaning |
| :--- | :--- | :--- |
| `episode_id` | `Episode ID` | Canonical episode key |
| `scene_id` | `Scene ID` | Canonical scene key |
| `environment_relation` | `Environment Relation` | Reuse/new/variant decision |
| `base_environment_reference` | `Base Environment Reference` | Canonical mother reference image/anchor for same venue |
| `environment_delta` | `Environment Delta` | Only changed visual factors relative to base reference |
| `observer_view` | `Observer View` | Camera observer placement + direction + axis side |
| `entry_state` | `Entry State` | Start snapshot for continuity |
| `exit_state` | `Exit State` | End snapshot for continuity |

## Environment Relation Decision Rule
- `NEW`: first creation of a scene environment variant.
- `REUSE:<EnvName>`: exact reuse (structure/view/light/background set unchanged).
- `VARIANT_OF:<EnvName>`: same venue family but required split due to axis/view/background/light/significant composition change.
- Base-reference rule: all same-venue variants inherit one `Base Environment Reference`; all changes must be declared as `Environment Delta`.
- Delta-only rule: anything not listed in `Environment Delta` is treated as inherited unchanged from base.
- Delta whitelist order rule: `Environment Delta` must keep fixed order `Camera Position/Direction -> Axis Side -> Background Set Change -> Lighting Direction Change -> Framing Change -> Dynamic Parts State`.
- Delta shorthand anchor: `CPD -> AS -> BG -> LD -> FR -> DP`.
- DP reason rule: whenever `DP` (`Dynamic Parts State`) is non-`None`, it must include `Before -> After` plus explicit `reason`.
- DP compliant example: `Dynamic Parts State: PROP:[Door](Open -> Closed, reason: CHAR:[@Character A] closes it quietly to avoid detection)`.
- DP non-compliant example: `Dynamic Parts State: Door: Closed` (missing `Before` and `reason`).
- DP non-compliant rewrite: `Dynamic Parts State: PROP:[Door](Open -> Closed, reason: CHAR:[@Character A] shuts the door before hiding behind the cabinet)`.
- REUSE minimal rule: for `REUSE`, default six delta keys are `None`; only `Dynamic Parts State` may be non-`None` when dynamic-part state actually changes.

## Beat-Level Minimum (Scene-Side)
- Beats must be time-ordered and action-causal.
- Beats must be spatially activated in scene space (no vacuum performance).
- Beats must carry camera-observer POV (`镜头位置`, `镜头朝向`, `角色-镜头关系`) and at least one framing parameter (`景别` or `镜高/俯仰`).
- Beat single-line minimum template (copy-ready): `1. {镜头:机位在{ }旁/朝向{ }/轴线{左侧|右侧}} + {空间:CHAR:[@角色A]在{ }相对{Stage}位于{ }} + {角色-镜头关系:CHAR:[@角色A]处于{前景|中景|后景}偏{左|右}、{正对|侧对|背对}镜头、景别{远景|全景|中景|近景|特写}、镜高/俯仰{平视|俯拍|仰拍}} + {主体关系:CHAR:[@角色A]与CHAR:[@角色B]位置{ }/朝向{ }/视线{ }/接触{ }} + {动作变化:因{触发原因}执行{动作路径与顺序}，对白/字幕/音效:{ }} -> {新状态:{位置|朝向|视线|接触|道具状态}}`.
- Hard validation: if any required slot in the minimum template is missing, empty, or replaced by abstract summary text, the Beat is invalid and must be rewritten with all slots filled.
- Beats should use explicit entity references in `[]` where required by prompt rules.
- Include enhancement constraints when instructed (e.g.,角色高光, 视觉转场).
- Beat sequence must support stable start/end states for shot decomposition.

## Validation Checklist (Cross-Stage)
- IDs are canonical and zero-padded (`EPxx`, `EPxx_SCyy`, `EPxx_SCyy_SHzz`).
- One-to-many hierarchy holds (`Episode -> Scenes -> Shots`).
- `Scene ID` prefix matches `Episode ID`.
- `Shot ID` prefix matches `Scene ID`.
- `Environment Relation` is present and valid in scene-bearing stages.
- `Base Environment Reference` is present for same-venue scenes and is stable across variants.
- `Environment Delta` only lists changed factors; `REUSE` rows explicitly declare `None` / `No visual delta`.
- `Environment Delta` respects whitelist order with all six keys present (unchanged keys must be `None`).
- Shorthand mapping consistency is preserved: `CPD=Camera Position/Direction`, `AS=Axis Side`, `BG=Background Set Change`, `LD=Lighting Direction Change`, `FR=Framing Change`, `DP=Dynamic Parts State`.
- If `DP` is non-`None` (including in `REUSE` rows), it must include explicit `Before -> After + reason`; otherwise validation fails.
- `REUSE` rows follow minimal delta form (five fixed `None`, optional non-`None` only on `DP`).
- `Observer View` is present and consistent with axis direction in scene-bearing stages.
- `Entry State` / `Exit State` are present and logically hand off between adjacent scenes.
- Beat-level camera observer descriptors are present and use a stable left/right reference basis.
- Axis/background/view changes trigger `VARIANT_OF` rather than silent reuse.
- Character/subject references use `CHAR:[@Name]` consistently; missing `@` on characters is invalid.
- Environment/prop references remain `[Name]` without `@`; `[@Env]` / `[@Prop]` are invalid.
- Entity typing is explicit and consistent: `CHAR:[@Name]`, `ENV:[Name]`, `PROP:[Name]`.
- Any type mismatch (`CHAR` used for env/prop, or `ENV/PROP` used for character) is invalid and must be rewritten.

## Maintenance Rule
When any key/label/ID format changes in one prompt, update all affected prompts and this matrix in the same change.
