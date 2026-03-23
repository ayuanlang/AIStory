# APIYI Import Readiness Review

Generated at: 2026-03-17T13:21:01.155144+00:00

## Extraction Coverage

- Public `modelPricing` rows scraped: 457
- Catalog models after docs merge: 461
- Docs-only models added beyond public pricing: 6

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

- Runtime-ready subset now includes APIYI image rows on /v1/images/generations, official async video rows on /v1/videos, and validated Sora reverse chat/completions video rows.
- Remaining APIYI rows stay deprecated/inactive staging data until their endpoint family is adapter-validated.
- Endpoint hints and pricing metadata are retained for future adapter work; unsupported endpoint families remain blocked.
- Billing rules use public APIYI sell prices directly, converted as `USD * 100 -> credits` with no extra multiplier.
- Hybrid-pricing docs are normalized to a single base rule when one primary public/default price exists; alternate billing modes stay in supplier notes only.
- LLM rows and unvalidated APIYI endpoint families remain blocked until they are explicitly re-enabled.

## Recommended Next Step

1. Import the APIYI bundle so all rows stay synchronized as managed system API data.
2. Apply the prepared base billing rules to the imported rows.
3. Activate only the runtime-ready subset in environments where API keys and provider grouping are configured correctly.
