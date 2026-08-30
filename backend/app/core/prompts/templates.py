# Core Entity Generation Templates
# Shared between Scene Analysis and Single Entity Analysis to ensure consistency.

# Fixed-syntax markers for bilingual prompt validation.
# Each generated prompt should include all markers for its entity type.
PROMPT_TEMPLATE_SYNTAX_RULES = {
	"characters": {
		"en_required": [
			"[Global Style]",
			"4-view character sheet",
			"16:9",
			"Structure: 4-view layout",
			"Close-up",
			"Front",
			"Side",
			"Back",
			"full-body",
			"Background: light gray",
		],
		"cn_required": [
			"四视图",
			"特写",
			"正面",
			"侧面",
			"反面",
			"全身",
			"背景",
			"浅灰",
		],
	},
	"props": {
		"en_required": [
			"[Global Style] Prop:",
			"4-view prop sheet",
			"16:9",
			"Structure: 4-view layout",
			"Scale-reference composite",
			"Side",
			"Back",
			"Background: light gray",
		],
		"cn_required": [
			"道具",
			"四视图",
			"尺度对照",
			"侧面",
			"反面",
			"背景",
			"浅灰",
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

1. Close-up: facial close-up with Neutral/Standard expression (Mandatory for reference), clear eyes, lips, makeup, and skin detail. This is the ONLY panel that may render a face.
2. Full-body Front: strict head-to-toe front standing pose, including footwear; do NOT generate the face — fill the facial region (hairline to chin, including eyes/nose/mouth) with the same light gray background color so the figure is faceless; keep hair silhouette, neck, clothing, and body.
3. Full-body Side: strict head-to-toe true side standing pose, including footwear, ear, hairline, shoulder slope, and body profile; cover the visible profile face with the same light gray background color; no facial features.
4. Full-body Back: strict head-to-toe rear standing pose, showing clothing seams, skirt hem, shoes, collar, and overall back silhouette; keep the back of the head and hair; no face; if any facial features leak, cover them with the light gray background.

Height: 【cm】; head-to-body ratio: 【ratio】. For named major adult roles, both fields are mandatory and must be explicit; if the script does not lock a different body type, default to a tall, camera-friendly silhouette at about 1:9.
Golden-ratio body balance rule (mandatory): for named major adult roles, default to a near golden-section body read with visibly longer legs than torso, a waist/hip break above the total-height midpoint, and a clear non-1:1 upper/lower-body split unless canon explicitly requires the opposite.
Named-character diffusion rule (mandatory): premium lead-grade beautification, hairstyle organization, wardrobe finish, accessory completion, and camera-friendly lighting should extend to all explicitly named adult roles, not just the absolute protagonist. Unless canon explicitly requires shabby, bulky, elderly, ill, exhausted, or low-status degradation, do not design named adult characters as passerby-level filler.
Basic role positioning: 【role positioning, e.g. female teacher / male detective / young conservatory pianist】.
Clothing: 【layers, materials, colors, wear】; include footwear and skirt fit. Also include a concise fashion benchmark that is compatible with the role positioning and project language context: specify current mainstream style direction, silhouette/material/color references, and contemporary wardrobe keywords grounded in present-day fashion knowledge rather than generic "stylish" wording. For explicitly named adult roles, if story facts, era, profession, safety boundaries, climate, and action functionality do not require the opposite, prefer fitted, tailored, body-following, silhouette-readable wardrobe rather than arbitrary baggy or shapeless clothing. This is a silhouette-control rule, not an explicit-sexualization rule, and it does not apply to minors or canonically loose/protective garments.
Distinctive anchors: 【scar, tattoo, accessory, emblem】 at 【location】.
Stable-anchor rule (mandatory): choose identity-stable, cross-shot persistent anchors only (e.g., bone/facial structure, fixed hairstyle silhouette, permanent marks, stable body proportion cues, long-term fixed accessories/garment structure). Do NOT use unstable cues as anchors: expressions, transient emotions, temporary poses/gestures, lighting/shadow artifacts, viewpoint-angle-dependent appearance changes, motion blur, or occlusion shapes.
Anchor compactness rule (mandatory): keep anchor_description concise and information-dense, usually 3 to 5 short English anchor phrases only. It should briefly cover the entity's core identity for reference-image retrieval: basic role positioning or identity, one or two stable appearance cues (face shape / hair silhouette / body outline), and only the most discriminative wardrobe or accessory cue when that cue genuinely helps distinguish the subject. The first anchor should usually be the subject's basic role positioning in English (for example: female teacher, female investigative reporter, male chef), followed by only the most stable visual identifiers.
Shared-wardrobe avoidance rule (mandatory): when multiple interacting characters plausibly wear the same wardrobe class, such as suits, uniforms, school uniforms, lab coats, or other group clothing, do not waste anchor slots on generic phrases like black suit or standard uniform. Shift anchor_description toward more discriminative cues first, such as face shape, hairstyle silhouette, body outline, signature accessory, shoe profile, wearing method, or uniquely readable garment construction details. Only keep wardrobe language when the garment itself has a clearly distinctive cut/detail.
Expression usage boundary: expressions in view instructions are display-only for shot variety and must never be treated as identity anchors.
Action traits: poised, controlled movements.
Lighting design: key light 【source position + quality (soft/hard) + intensity + color temperature】, fill light 【ratio/intensity】, rim/back light 【direction】; keep the close-up face readable and silhouette separated. For protagonist shaping, prioritize beauty-lighting setups (e.g., butterfly/paramount light, clamshell fill, soft frontal diffusion, controlled catchlights) to enhance facial attractiveness while preserving realism.
Lens & focus: 【focal length / equivalent lens, e.g. 35mm / 50mm / 85mm】 + 【focus strategy, e.g. deep focus / shallow DOF】.
Texture/noise: 【film grain level, e.g. clean digital / fine film grain / medium grain】, skin texture retention 【level】, avoid over-smoothing.
Style adaptation by script type: if [Global Style] indicates live-action / realistic drama, enforce photoreal human anatomy, natural pores and micro-texture, realistic eye specular highlights, physically plausible subsurface skin response, and avoid CGI/plastic look. In this mode, protagonist close/medium shots should default to refined beauty-lighting first, then adjust contrast by genre mood.
Background: light gray.
anchor_description：【concise identity + appearance + wardrobe retrieval anchors】.
Style: follow [Global Style].
Canvas rule: treat the character sheet as a 16:9 horizontal asset canvas aligned to the system subject asset ratio; do not introduce any conflicting portrait or square sheet ratio.
Layout rule: asymmetrical 4-panel sheet. The Close-up must sit in the FIRST panel on the LEFT as a large full-height panel occupying about 40% of the total canvas width. The remaining 60% on the RIGHT must be split into three equal stacked panels in the strict order Full-body Front, Full-body Side, Full-body Back. All four views must stay fully inside their own panels with complete silhouettes and zero cropping.
Minor-safety rule: if the character is a minor, child, kid, preteen, teen, toddler, baby, or infant, the layout requirement does NOT change. Still render the exact same 4-view character sheet with Close-up, Full-body Front, Full-body Side, and Full-body Back; do not downgrade to a single portrait, a single full-body concept image, a looser child-only composition, or any instruction implying no 4-panel layout. The only age-specific adaptation is safety: keep wardrobe, pose, camera intent, and wording fully age-appropriate, non-sexualized, non-fetishized, and strictly non-NSFW.
Close-up crop rule: in the FIRST LEFT close-up panel, the face must sit on the vertical centerline and remain vertically centered in the panel, not drifting to the top, bottom, or side. The head should occupy about 78% to 88% of the panel height so the close-up reads clearly larger than the other three views, while the full hair silhouette, chin line, and neck transition remain complete. Keep background margin tight and balanced on all sides rather than leaving empty space.
Right-panel framing rule: the three RIGHT full-body panels must use the same framing scale and the same padding logic. Make them slightly smaller than the close-up in visual dominance, but keep top margin and foot margin uniformly minimal while reducing left-right padding further so each figure reads larger without cropping. Each figure should occupy about 84% to 89% of each panel height, with head, feet, footwear, hems, and outer silhouette fully visible and never cropped. Full-body face-cover rule (mandatory): on Full-body Front, Side, and Back, do not generate a face; paint the facial region with the canvas light gray so those three panels are faceless. Keep hair silhouette. Do not use mosaic, black bars, blur, or a semi-transparent face.
Structure: 4-view layout (First panel = larger centered Close-up on the left; right column = Full-body Front, Full-body Side, Full-body Back).
Panel finish rule: zero gutter, zero blank spacing, no collage seam, no divider line, no white border, no black border, no framing bar; the panel boundaries may exist compositionally but must not render as visible lines.
Output: deliver a 16:9 4-panel composite asset sheet, or four source renders assembled to the same 16:9 sheet; include a simple scale marker; no labels, no captions, no watermark; End note: light gray background, high quality, large files, no text.
"""

PROP_PROMPT_TEMPLATE = """
[Global Style] Prop: 【PropName (state)】, 4-view prop sheet — all four views must show the same object identity, proportions, material response, and anchor details consistently, in the strict order: Scale-reference composite (near), Scale-reference composite (front), Side, Back.

1. Scale-reference composite (near, first panel): the prop and ONE standardized scale-reference entity share the same cell but stay completely isolated — no touching, overlapping, holding, or wearing. Use the extracted linear-diagram name (adult female/male figure, palm, ear, neck, wrist; or ping-pong ball, basketball, standard truck, building) and the extracted length/height/width ratios vs that reference (e.g. L=1/2 palm length, H=2/3 palm width, T≈1/6 palm thickness). Annotate L=/H=/T= length and V= volume with English unit abbreviations (mm, cm, m, cm3, mL, L, m3).
2. Scale-reference composite (front, second panel): the same prop and the SAME isolated reference entity share the same cell at full-front silhouette, with the same numeric annotations and a visible gray gap between them.
3. Full Side: true side profile of the prop only (no reference, no people), showing thickness/depth and contour.
4. Full Back: full object rear view of the prop only, with seams, back panel, and structure continuity.

Structure: 4-view layout (Scale-reference composite, Scale-reference composite front, Side, Back).
Material: 【primary_material】; secondary materials: 【list】.
Size: 【number + English unit, e.g. L=86mm, H=54mm, V=18cm3】.
Relative scale reference: 【standardized reference + L/H/W ratios vs that reference, e.g. adult-female-palm line drawing, L=1/2 palm length, H=2/3 palm width, T≈1/6 palm thickness】.
Visible details: 【surface texture, wear, markings, seams, labels】.
Lighting setup: key/fill/rim 【direction + intensity + color_temp + soft/hard】.
Lens & focus: 【focal length / equivalent lens + DOF strategy】.
Grain/noise strategy: 【clean digital / fine film grain / medium grain】 with readable texture in shadows.
Style adaptation by script type: live-action/realistic drama must enforce physically plausible material response (metal specular, fabric fibers, roughness variation), true-to-scale wear, and avoid toy-like/plastic CGI look.
anchor_description：【Chinese L/H/W ratios vs reference + numeric units, e.g. 长=1/2掌长｜高=2/3掌宽｜宽≈1/6掌厚, 86mm L, 54mm H, 18cm3 V】 plus 1–3 English material/structure phrases.
Background: light gray.
Narrative-isolation rule: no story character, no photoreal holding/wearing/using. First two panels MUST include the standardized linear scale-reference entity as a second, fully isolated subject (visible gap, no contact); panels 3–4 are prop-only.
Canvas rule: treat the prop sheet as a 16:9 horizontal asset canvas aligned to the system subject asset ratio; do not introduce any conflicting portrait or square sheet ratio.
Layout rule: asymmetrical 4-panel sheet. The first scale-reference composite sits in the FIRST panel on the LEFT occupying about 35% of the total canvas width, vertically centered. The remaining 65% on the RIGHT holds Front composite, Side, Back. All four views must stay fully inside their own panels with complete silhouettes and zero cropping.
Panel finish rule: zero gutter, zero blank spacing, no collage seam, no divider line, no white border, no black border, no framing bar; the panel boundaries may exist compositionally but must not render as visible lines.
Output: deliver a 16:9 4-panel composite asset sheet; first two panels show prop + scale reference with numeric L/H/V annotations; side and back are prop-only; no watermark; End note: light gray background, high quality, large files.
"""

ENVIRONMENT_PROMPT_TEMPLATE = """
[Global Style] Viewpoint at 【viewpoint_height_and_angle】 looking 【view_direction】 into 【environment_name】; focal point 【primary_anchor_feature】 at 【relative_position】; entrance 【position】; main circulation width ≈ 【width】; actionable area (m) 【action_area_dimensions】. Center the prompt on the Stage/core playable zone: spell out the exact fixed stage entities 【stage_entity_set】, their boundary relationship 【stage_boundaries】, playable standing surfaces 【playable_surfaces】, and the concrete traversal route 【entry->action->exit route】 rather than using abstract area labels. If the beat logic implies any threshold or interface-crossing travel, explicitly describe the interface pair 【interior/exterior threshold, opening edge, sill/rim, near-side standing zone, far-side landing zone】, passable clearance 【minimum passable gap】, turning pocket 【turning/hold position】, and sightline continuity on both sides. Treat doorways, cave mouths, window openings, desk front/back positions, counter outside/inside positions, stage edge crossings, and similar boundary pairs with the same concrete spatial discipline. Maintain theatrical stage-space rationality: core stage zone 【center + dimensions】, sightline clarity 【front/reverse observer readability】, Viewpoint Movement corridor 【dolly/pan clearance】, obstacle/safety clearance 【minimum passable gap】, and physical reachability for all scripted beats. Architectural anchors 【key_features】; materials: floor 【floor_material】, walls 【wall_finish】, ceiling 【ceiling_detail】; scale reference 【scale_reference】 (include 1m scale bar); depth: foreground 【foreground_elements】, midground 【midground_elements】, background 【background_elements】, negative space 【negative_space】; time 【time_of_day】; lighting setup: key/fill/back 【position,intensity,color_temp + soft/hard】; lens & focus baseline 【focal length family + DOF strategy】; grain/noise strategy 【clean digital / fine film grain / medium grain】; color palette: dominant 【dominant_colors】, accents 【accent_colors】; mood 【mood_adjectives】. Style adaptation by script type: live-action/realistic drama should prioritize physically plausible architecture scale, practical lighting motivation, and photoreal material response; avoid game-like/CGI set feeling. anchor_description：【thumbnail_readability】. **No people or characters in scene.**
"""
