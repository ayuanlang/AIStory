# Scene Analysis Feature Stack

This package adds a routed scene-analysis base prompt plus runtime feature skills for the non-classic path.

Goals:
- Keep `classic` on the original `scene_analysis.txt` path.
- Use a separate routed base prompt for `feature_stack` and `decision_engine`.
- Preserve a parallel configurable path beside the original prompt-only path.
- Normalize project features into a finite set of dimensions.
- Support a decision-engine route that can infer dimensions from project info and script text.
- Render only matched dimension and combo skills into explicit routed slots without changing the output contract.

Runtime flow:
1. `AnalyzeSceneRequest.scene_analysis_mode` selects `classic`, `feature_stack`, or `decision_engine`.
2. `AnalyzeSceneRequest.scene_analysis_features` overrides or supplements `project_metadata`.
3. `scene_analysis_feature_skills.py` resolves dimensions from explicit input, project metadata, and optionally script text inference.
4. The decision engine selects matched dimension skills and combo skills.
5. Registry entries can provide atomic `global/environment/character/prop/character_goal_alignment` fragments for explicit local slot routing.
6. Combo local fragments use dedicated combo slots instead of reusing the `project_type` local slots.
7. The analyze_scene endpoint loads the routed base prompt for non-classic modes and renders the selected slot blocks into the prompt.
8. The routed base prompt keeps the same output contract, while `classic` still uses the original `scene_analysis.txt`.

Dual-goal support:
- `primary_goal` and `secondary_goal` can be used together.
- This is intended for cases like `script_optimization + character_creation`.
- In dual-goal mode, character design is expected to serve plot function, conflict structure, and relationship evolution.

Design principles:
- Use atomic skills by dimension instead of building hard-coded combinational prompts.
- Keep skill fragments short and bias-focused.
- Prefer explicit atomic registry fragments over auto-scoping one large prompt wherever a dimension or combo has clear local behavior.
- Add combo rules only when they express real route differences that cannot be captured by one single dimension.
- Expose the enum catalog so frontend/tooling can present explicit feature selectors.

Current implemented decision dimensions:
- project_type
- project_language
- base_positioning
- era_setting
- region_culture
- expected_model_family
- generation_workflow
- primary_goal
- secondary_goal
- character_emphasis
- narrative_density
- commercial_constraint
- modality_focus
- continuity_priority
- safety_broadcast_level