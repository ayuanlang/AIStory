# Runtime Enum Mapping Rules

## Purpose
Define deterministic runtime enum mapping for provider payload construction.
This document is the single source of truth for LLM planning and backend implementation.

## Core Principle
All provider-facing enum fields must be mapped to each API's allowed values before submit.

Mapping order:
1. Exact match (case-insensitive) in allowed enum.
2. Canonical/alias normalization match (e.g. mode synonyms).
3. Numeric-near mapping for numeric-like enums.
4. Conservative fallback to allowed minimum/baseline enum value.

- Never emit values outside provider enum list.

## Dimension Rules

### duration (seconds)
Nearest-lower mapping.

- Input value already in enum: keep as-is.
- Input value not in enum: map to the nearest allowed value that is less than or equal to input.
- If input is lower than all allowed values: map to the minimum allowed value.

### image_size
Nearest-lower mapping on normalized numeric rank.

- Supported parsing examples: `1K`, `2K`, `4K`, `k2`, `1024x1024`.
- If request value cannot be parsed as numeric rank: fallback to allowed baseline.

### resolution
Nearest-lower mapping on normalized resolution tier.

- Supported parsing examples: `720p`, `1080P`, `1280x720`, `1024:768`.
- Resolution tier uses shorter side for WxH forms.

### aspect_ratio
Nearest-ratio mapping.

- Exact match first.
- If request is a ratio-like value, map to allowed ratio with minimal numeric distance.
- Built-in normalization includes `2.35:1`/`2.39:1` -> `21:9`.

### mode
Canonical enum remap.

- Exact match first.
- Then map via canonical mode normalization (e.g. `standard` <-> `std`).
- If still unmatched, fallback to allowed baseline mode.

## Duration Mapping Rule
Applicable to video/voice duration normalization.

Given requested duration R and allowed set A (positive integers):
1. Sort and deduplicate A ascending.
2. Find subset L = { x in A | x <= R }.
3. If L is not empty, mapped duration = max(L).
4. Else mapped duration = min(A).

Examples:
- A=[5,10], R=7.5 -> 5
- A=[5,10], R=10 -> 10
- A=[5,10], R=9 -> 5
- A=[5,10], R=3 -> 5
- A=[4,6,8], R=7 -> 6

## Kling 2.6 Image-to-Video Hard Constraint
Model: kling-2.6/image-to-video

- If runtime enum catalog has durations_seconds, apply nearest-lower mapping using that set.
- If durations_seconds is missing/empty, fallback allowed durations must be [5, 10].
- Payload duration must be one of provider-allowed values only.

## Global Payload Safety Rule
Before submit, final enum guard must re-apply all enum mappings (`mode`, `aspect_ratio`, `image_size`, `resolution`, `duration`) to prevent accidental out-of-enum values from intermediate transforms.

## Implementation References
- backend/app/services/media_service.py
  - _map_duration_nearest_lower
  - _map_mode_to_allowed
  - _map_aspect_ratio_to_allowed
  - _map_image_size_to_allowed
  - _map_resolution_to_allowed
  - _apply_runtime_enum_constraints
  - KIE video payload assembly
  - final enum guard before HTTP submit

## Notes for LLM Planners
- Do not output provider-unsupported enum candidates.
- Prefer enum candidates directly when possible.
- When unsure of provider enum, use runtime catalog if available.
- For numeric-like fields, prefer nearest-lower candidate from runtime catalog.
- For kling-2.6/image-to-video, default duration candidate set is [5,10].
