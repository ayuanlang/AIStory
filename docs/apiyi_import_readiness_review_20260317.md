# APIYI Import Readiness Review

Generated at: 2026-03-17T13:21:01.155144+00:00

## Extraction Coverage

- Public `modelPricing` rows scraped: 457
- Catalog models after docs merge: 461
- Docs-only models added beyond public pricing: 5

## Category Counts

- Image: 36 models (36 priced)
- LLM: 390 models (389 priced)
- Video: 35 models (35 priced)

## Billing Rules

- Base billing rules prepared: 460
- `per_million_tokens`: 352
- `per_call`: 108
- `per_second`: 0
- Unresolved pricing rows skipped: 1

## Import Posture

- APIYI LLM rows are kept deprecated/inactive staging rows.
- APIYI Image rows with `/v1/images/generations` and Video rows with `/v1/videos` are imported as runtime-ready, non-deprecated rows.
- APIYI chat-completions media variants and Google native image endpoints remain deprecated/inactive staging rows.
- Billing rules use public APIYI sell prices directly, converted as `USD * 100 -> credits` with no extra multiplier.
- Hybrid-pricing docs are normalized to a single base rule when one primary public/default price exists; alternate billing modes stay in supplier notes only.
- Runtime activation remains blocked for Google native image endpoints and media chat-completions variants until dedicated adapters exist.

## Recommended Next Step

1. Import the APIYI bundle so the Image `/v1/images/generations` and Video `/v1/videos` subsets become selectable at runtime.
2. Apply the prepared base billing rules to the imported rows.
3. Review remaining APIYI chat-completions media variants and Google-native image adapters before broader activation.
