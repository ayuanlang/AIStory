# Core Entity Generation Templates
# Shared between Scene Analysis and Single Entity Analysis to ensure consistency.

# Fixed-syntax markers for bilingual prompt validation.
# Each generated prompt should include all markers for its entity type.
PROMPT_TEMPLATE_SYNTAX_RULES = {
	"characters": {
		"en_required": [
			"[Global Style]",
			"4-view character sheet",
			"Structure: 4-view layout",
			"Close-up",
			"Front",
			"Side",
			"Back",
			"full-body",
			"Background: white",
		],
		"cn_required": [
			"四视图",
			"特写",
			"正面",
			"侧面",
			"反面",
			"全身",
			"背景",
			"纯白",
		],
	},
	"props": {
		"en_required": [
			"[Global Style] Prop:",
			"4-view prop sheet",
			"Structure: 4-view layout",
			"Close-up",
			"Front",
			"Side",
			"Back",
			"Background: white",
			"Strictly Object Only",
		],
		"cn_required": [
			"道具",
			"四视图",
			"特写",
			"正面",
			"侧面",
			"反面",
			"仅物体",
			"背景",
			"纯白",
		],
	},
	"environments": {
		"en_required": [
			"[Global Style] Viewpoint at",
			"No people or characters in scene",
		],
		"cn_required": [
			"环境",
			"无人物",
			"背景",
		],
	},
}

CHARACTER_PROMPT_TEMPLATE = """
[Global Style], 4-view character sheet — all four views must show the same character, outfit, proportions, and anchors consistently, in the strict order: Close-up, Full-body Front, Full-body Side, Full-body Back.

1. Close-up: facial close-up with Neutral/Standard expression (Mandatory for reference), clear eyes, lips, makeup, and skin detail.
2. Full-body Front: strict head-to-toe front standing pose, including footwear, face visible, key facial features.
3. Full-body Side: strict head-to-toe true side standing pose, including footwear, ear, hairline, shoulder slope, and body profile.
4. Full-body Back: strict head-to-toe rear standing pose, showing clothing seams, skirt hem, shoes, collar, and overall back silhouette.

Height: 【cm】; head-to-body ratio: 【ratio】.
Clothing: 【layers, materials, colors, wear】; include footwear and skirt fit.
Distinctive anchors: 【scar, tattoo, accessory, emblem】 at 【location】.
Stable-anchor rule (mandatory): choose identity-stable, cross-shot persistent anchors only (e.g., bone/facial structure, fixed hairstyle silhouette, permanent marks, stable body proportion cues, long-term fixed accessories/garment structure). Do NOT use unstable cues as anchors: expressions, transient emotions, temporary poses/gestures, lighting/shadow artifacts, viewpoint-angle-dependent appearance changes, motion blur, or occlusion shapes.
Expression usage boundary: expressions in view instructions are display-only for shot variety and must never be treated as identity anchors.
Action traits: poised, controlled movements.
Lighting design: key light 【source position + quality (soft/hard) + intensity + color temperature】, fill light 【ratio/intensity】, rim/back light 【direction】; keep face readable and silhouette separated. For protagonist shaping, prioritize beauty-lighting setups (e.g., butterfly/paramount light, clamshell fill, soft frontal diffusion, controlled catchlights) to enhance facial attractiveness while preserving realism.
Lens & focus: 【focal length / equivalent lens, e.g. 35mm / 50mm / 85mm】 + 【focus strategy, e.g. deep focus / shallow DOF】.
Texture/noise: 【film grain level, e.g. clean digital / fine film grain / medium grain】, skin texture retention 【level】, avoid over-smoothing.
Style adaptation by script type: if [Global Style] indicates live-action / realistic drama, enforce photoreal human anatomy, natural pores and micro-texture, realistic eye specular highlights, physically plausible subsurface skin response, and avoid CGI/plastic look. In this mode, protagonist close/medium shots should default to refined beauty-lighting first, then adjust contrast by genre mood.
Background: white.
anchor_description：【thumbnail_readability】.
Style: follow [Global Style].
Structure: 4-view layout (Close-up, Full-body Front, Full-body Side, Full-body Back).
Output: four high-resolution PNGs or a 4-panel composite; include a simple scale marker; no labels, no captions, no watermark; End note: white background, high quality, large files, no text.
"""

PROP_PROMPT_TEMPLATE = """
[Global Style] Prop: 【PropName (state)】, 4-view prop sheet — all four views must show the same object identity, proportions, material response, and anchor details consistently, in the strict order: Close-up, Front, Side, Back.

1. Close-up: macro close-up of key surface/material detail (texture, wear, marking, label).
2. Full Front: full object front view with complete silhouette and readable major geometry.
3. Full Side: true side profile showing thickness/depth and contour.
4. Full Back: full object rear view with seams, back panel, and structure continuity.

Structure: 4-view layout (Close-up, Front, Side, Back).
Material: 【primary_material】; secondary materials: 【list】.
Size: ~【dimensions cm or relative to reference】.
Relative scale reference: 【reference_subject e.g., belt buckle, chair】.
Visible details: 【surface texture, wear, markings, seams, labels】.
Lighting setup: key/fill/rim 【direction + intensity + color_temp + soft/hard】.
Lens & focus: 【focal length / equivalent lens + DOF strategy】.
Grain/noise strategy: 【clean digital / fine film grain / medium grain】 with readable texture in shadows.
Style adaptation by script type: live-action/realistic drama must enforce physically plausible material response (metal specular, fabric fibers, roughness variation), true-to-scale wear, and avoid toy-like/plastic CGI look.
anchor_description：【thumbnail_readability】.
Background: white.
**Strictly Object Only: No characters, no hands, no body parts visible.**
Output: four high-resolution PNGs or a 4-panel composite; include a simple, unobtrusive scale marker (no numbers/text); no labels, no captions, no watermark; End note: white background, high quality, large files, no text.
"""

ENVIRONMENT_PROMPT_TEMPLATE = """
[Global Style] Viewpoint at 【viewpoint_height_and_angle】 looking 【view_direction】 into 【environment_name】; focal point 【primary_anchor_feature】 at 【relative_position】; entrance 【position】; main circulation width ≈ 【width】; actionable area (m) 【action_area_dimensions】. Center the prompt on the Stage/core playable zone: spell out the exact fixed stage entities 【stage_entity_set】, their boundary relationship 【stage_boundaries】, playable standing surfaces 【playable_surfaces】, and the concrete traversal route 【entry->action->exit route】 rather than using abstract area labels. If the beat logic implies any threshold or interface-crossing travel, explicitly describe the interface pair 【interior/exterior threshold, opening edge, sill/rim, near-side standing zone, far-side landing zone】, passable clearance 【minimum passable gap】, turning pocket 【turning/hold position】, and sightline continuity on both sides. Treat doorways, cave mouths, window openings, desk front/back positions, counter outside/inside positions, stage edge crossings, and similar boundary pairs with the same concrete spatial discipline. Maintain theatrical stage-space rationality: core stage zone 【center + dimensions】, sightline clarity 【front/reverse observer readability】, Viewpoint Movement corridor 【dolly/pan clearance】, obstacle/safety clearance 【minimum passable gap】, and physical reachability for all scripted beats. Architectural anchors 【key_features】; materials: floor 【floor_material】, walls 【wall_finish】, ceiling 【ceiling_detail】; scale reference 【scale_reference】 (include 1m scale bar); depth: foreground 【foreground_elements】, midground 【midground_elements】, background 【background_elements】, negative space 【negative_space】; time 【time_of_day】; lighting setup: key/fill/back 【position,intensity,color_temp + soft/hard】; lens & focus baseline 【focal length family + DOF strategy】; grain/noise strategy 【clean digital / fine film grain / medium grain】; color palette: dominant 【dominant_colors】, accents 【accent_colors】; mood 【mood_adjectives】. Style adaptation by script type: live-action/realistic drama should prioritize physically plausible architecture scale, practical lighting motivation, and photoreal material response; avoid game-like/CGI set feeling. anchor_description：【thumbnail_readability】. **No people or characters in scene.**
"""
