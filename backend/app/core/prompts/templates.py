# Core Entity Generation Templates
# Shared between Scene Analysis and Single Entity Analysis to ensure consistency.

# Fixed-syntax markers for bilingual prompt validation.
# Each generated prompt should include all markers for its entity type.
PROMPT_TEMPLATE_SYNTAX_RULES = {
	"characters": {
		"en_required": [
			"[Global Style]",
			"6-view character sheet",
			"Structure: 6-view layout",
			"Front",
			"Back",
			"Side",
			"3/4",
			"Close-up",
			"Detail",
			"Background: white",
		],
		"cn_required": [
			"六视图",
			"正面",
			"背面",
			"侧面",
			"四分之三",
			"特写",
			"细节",
			"背景",
			"纯白",
		],
	},
	"props": {
		"en_required": [
			"[Global Style] Prop:",
			"6-view prop sheet",
			"Structure: 6-view layout",
			"Front",
			"Back",
			"Side",
			"3/4",
			"Close-up",
			"Detail",
			"Background: white",
			"Strictly Object Only",
		],
		"cn_required": [
			"道具",
			"六视图",
			"正面",
			"背面",
			"侧面",
			"四分之三",
			"特写",
			"细节",
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
[Global Style], 6-view character sheet — all six views must show the same character, outfit, proportions, and anchors consistently.

1. Full-body Front: standing pose with 【Expression 1: Character's Core Trait】, including footwear, face visible, key facial features.
2. Full-body Back: rear standing pose, showing clothing seams, skirt hem, shoes, collar, and necklace placement.
3. Half-body (Waist-up): torso view with 【Expression 2: Plot-relevant Emotion A】, shirt opening, necklace, hand position, fabric texture.
4. Close-up: facial close-up with Neutral/Standard expression (Mandatory for reference), clear eyes, lips, makeup, and skin detail.
5. Side Profile: true side view with 【Expression 3: Plot-relevant Emotion B】, showing full facial profile, ear, hairline, and shoulder slope.
6. Back Detail: rear detail of upper back and collar area, showing collar turn-out, necklace, and stitching.

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
Output: six high-resolution PNGs or a 6-panel composite; include a neutral T-pose reference and a simple scale marker; no labels, no captions, no watermark; End note: white background, high quality, large files, no text.
"""

PROP_PROMPT_TEMPLATE = """
[Global Style] Prop: 【PropName (state)】, 6-view prop sheet — all six views must show the same object identity, proportions, material response, and anchor details consistently.

1. Full Front: full object front view with complete silhouette and readable major geometry.
2. Full Back: full object rear view with seams, back panel, and structure continuity.
3. Full Side: true side profile showing thickness/depth and contour.
4. 3/4 View: front three-quarter view for volume and edge readability.
5. Close-up: macro close-up of key surface/material detail (texture, wear, marking, label).
6. Detail View: close detail of a critical anchor part (e.g., handle/joint/corner/fastener).

Structure: 6-view layout (Front, Back, Side, 3/4, Close-up, Detail).
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
Output: six high-resolution PNGs or a 6-panel composite; include a simple, unobtrusive scale marker (no numbers/text); no labels, no captions, no watermark; End note: white background, high quality, large files, no text.
"""

ENVIRONMENT_PROMPT_TEMPLATE = """
[Global Style] Viewpoint at 【viewpoint_height_and_angle】 looking 【view_direction】 into 【environment_name】; focal point 【primary_anchor_feature】 at 【relative_position】; entrance 【position】; main circulation width ≈ 【width】; actionable area (m) 【action_area_dimensions】; theatrical stage-space rationality: core stage zone 【center + dimensions】, actor path continuity 【entry->action->exit route】, sightline clarity 【front/reverse observer readability】, Viewpoint Movement corridor 【dolly/pan clearance】, obstacle/safety clearance 【minimum passable gap】, and physical reachability for all scripted beats. Architectural anchors 【key_features】; materials: floor 【floor_material】, walls 【wall_finish】, ceiling 【ceiling_detail】; scale reference 【scale_reference】 (include 1m scale bar); depth: foreground 【foreground_elements】, midground 【midground_elements】, background 【background_elements】, negative space 【negative_space】; time 【time_of_day】; lighting setup: key/fill/back 【position,intensity,color_temp + soft/hard】; lens & focus baseline 【focal length family + DOF strategy】; grain/noise strategy 【clean digital / fine film grain / medium grain】; color palette: dominant 【dominant_colors】, accents 【accent_colors】; mood 【mood_adjectives】. Style adaptation by script type: live-action/realistic drama should prioritize physically plausible architecture scale, practical lighting motivation, and photoreal material response; avoid game-like/CGI set feeling. anchor_description：【thumbnail_readability】. **No people or characters in scene.**
"""
