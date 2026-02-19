# Core Entity Generation Templates
# Shared between Scene Analysis and Single Entity Analysis to ensure consistency.

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
Action traits: poised, controlled movements.
Lighting: soft front light + rim light for silhouette.
Background: white.
anchor_description：【thumbnail_readability】.
Style: follow [Global Style].
Output: six high-resolution PNGs or a 6-panel composite; include a neutral T-pose reference and a simple scale marker; no labels, no captions, no watermark; End note: white background, high quality, large files, no text.
"""

PROP_PROMPT_TEMPLATE = """
[Global Style] Prop: 【PropName (state)】. Material: 【primary_material】; secondary materials: 【list】. Size: ~【dimensions cm or relative to reference】. Relative scale reference: 【reference_subject e.g., belt buckle, chair】. Visible details: 【surface texture, wear, markings, seams, labels】. Lighting for capture: 【direction, intensity, color_temp】; shadow behavior: 【soft/hard】. Camera framing: 【view e.g., front 3/4; macro insert】. anchor_description：【thumbnail_readability】. Background: white. **Strictly Object Only: No characters, no hands, no body parts visible.** Output: single object PNG with alpha; include a simple, unobtrusive scale marker (no numbers/text); End note: white background, high quality, large file, no text.
"""

ENVIRONMENT_PROMPT_TEMPLATE = """
[Global Style] Camera at 【camera_height_and_angle】 looking 【view_direction】 into 【environment_name】; focal point 【primary_anchor_feature】 at 【relative_position】; entrance 【position】; main circulation width ≈ 【width】; actionable area (m) 【action_area_dimensions】; architectural anchors 【key_features】; materials: floor 【floor_material】, walls 【wall_finish】, ceiling 【ceiling_detail】; scale reference 【scale_reference】 (include 1m scale bar); depth: foreground 【foreground_elements】, midground 【midground_elements】, background 【background_elements】, negative space 【negative_space】; time 【time_of_day】; lighting: key 【position,intensity,color_temp】, fill 【position,intensity,color_temp】, backlight 【position,intensity,color_temp】; shadow quality 【soft/hard】; color palette: dominant 【dominant_colors】, accents 【accent_colors】; mood 【mood_adjectives】; anchor_description：【thumbnail_readability】. **No people or characters in scene.**
"""
