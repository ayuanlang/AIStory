# RunningHub Full Catalog Import Readiness Review

Date: 2026-03-17

## Scope

- Source snapshot: `docs/runninghub_openapi_snapshot.full_catalog.json`
- Catalog size: 149 standard-model APIs
- Extraction mode: browser-rendered HTML fallback

## Extraction Coverage

- Parsed successfully: 149 / 149 (`parsed_html`)
- Zero-field pages: 0
- Missing endpoint: 0
- Missing method: 0
- Missing `sku_id`: 149 / 149

Category split:

- Video: 94
- Image: 35
- 3D: 12
- Voice: 7
- Music: 1

Service-tier split:

- official_stable: 25
- low_cost_channel: 22
- unknown: 102

## Standard Mapping Coverage

After expanding direct mappings to existing repository-standard dimensions, coverage is:

- Models with at least one direct field mapping: 148 / 149
- Direct field mappings: 462

Compared with the prior full-catalog review pass:

- Direct-mapped models: 143 -> 148
- Direct-mapped fields: 311 -> 462

Direct dimensions now covered by the RunningHub extractor:

- `TEXT_INPUT`
- `ASPECT_RATIO`
- `RESOLUTION_TIER`
- `FRAME_SIZE`
- `IMAGE_SIZE_CLASS`
- `DURATION_SECONDS`
- `MODE`
- `QUALITY_LEVEL`
- `OUTPUT_FORMAT`
- `REFERENCE_IMAGE_URL`
- `REFERENCE_IMAGE_URLS`
- `SOUND_SUPPORTED`
- `MULTI_SHOTS_SUPPORTED`
- `VOICE_ID`
- `EMOTION`
- `RETURN_BASE64`
- `ENGLISH_NORMALIZATION`
- derived: `GENERATION_MODE`
- derived: `SERVICE_TIER`

Highest-frequency mapped dimensions:

- `GENERATION_MODE`: 148
- `TEXT_INPUT`: 135
- `DURATION_SECONDS`: 75
- `RESOLUTION_TIER`: 68
- `ASPECT_RATIO`: 60
- `SERVICE_TIER`: 47
- `REFERENCE_IMAGE_URL`: 39
- `REFERENCE_IMAGE_URLS`: 28
- `SOUND_SUPPORTED`: 12
- `FRAME_SIZE`: 10

## Remaining Gaps

Highest-frequency unmapped source fields:

- `negativePrompt`: 29
- `firstImageUrl`: 20
- `lastImageUrl`: 20
- `enablePromptExpansion`: 14
- `videoUrl`: 13
- `movementAmplitude`: 11
- `keepOriginalSound`: 10
- `requestType`: 10
- `face`: 10
- `generateAudio`: 9
- `audio`: 8
- `seed`: 7
- `bgm`: 6
- `raw`: 6
- `elementList`: 6
- `leftImageUrl`: 6
- `rightImageUrl`: 6
- `backImageUrl`: 6
- `pronunciation_dict`: 6
- `speed`: 6
- `volume`: 6
- `pitch`: 6

These fall into a few unresolved standardization families:

- Negative prompt semantics: `negativePrompt`
- Multi-slot media references: `firstImageUrl`, `lastImageUrl`, `leftImageUrl`, `rightImageUrl`, `backImageUrl`, `videoUrl`, `audio`
- Video control knobs: `movementAmplitude`, `requestType`, `face`, `raw`, `elementList`
- Audio/TTS control knobs: `pronunciation_dict`, `speed`, `volume`, `pitch`, `generateAudio`, `keepOriginalSound`, `bgm`
- Reproducibility / generation toggles: `seed`, `enablePromptExpansion`

One model still has no direct field mapping at all:

- `全能视频S-角色上传-低价渠道版` (`/openapi/v2/rhart-video-s/sora-upload-character`)

That endpoint appears to be an upload/character-registration surface rather than a standard generation surface, so leaving it unmapped is acceptable for now.

## Import Readiness

Current status: ready for catalog import, not ready for full runtime standardization.

What is ready now:

- Full-catalog metadata import as deprecated/inactive `system_api_settings` rows
- Capability seeding for generation mode, tier, aspect ratio, duration, resolution, image refs, prompt/text input, mode, quality, output format, audio flags, and voice controls already covered above
- Review and selection inside system settings without activating the endpoints

What should still block automatic runtime activation:

- `sku_id` is absent on all 149 entries
- Several high-value semantic controls still lack agreed standard dimensions
- Upload-style and multi-reference endpoints need explicit runtime treatment instead of assuming generic text/image/video generation contracts

## Recommendation

Recommended next step:

1. Import the full RunningHub bundle in deprecated/inactive state for catalog staging only.
2. Keep runtime adapters disabled until the next standard-dimension pass covers at least:
   - negative prompt
   - seed
   - reference frame / reference video slots
   - audio prosody controls (`speed`, `volume`, `pitch`)
3. Treat upload-style endpoints separately from normal generation endpoints during activation review.

This means the extraction pipeline is complete and useful today, while the remaining work is policy-level normalization rather than parser reliability.