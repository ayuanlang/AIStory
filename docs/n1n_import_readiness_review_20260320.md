# n1n Import Readiness Review

Generated at: 2026-03-20T15:30:03.613742+00:00

## Extraction Coverage

- llms.txt API Docs entries parsed: 320
- Protocol profiles normalized: 46
- Import rows prepared: 46
- Pricing groups captured: 14
- Known fixed-price exceptions: 1

## Category Counts

- Image: 13
- LLM: 11
- Music: 1
- Tools: 1
- Video: 15
- Voice: 5

## Import Posture

- All n1n rows are kept deprecated/inactive staging rows.
- No n1n runtime activation is enabled in this bundle because the repo does not yet contain a provider adapter or provider-name promotion logic for n1n.
- OpenAI-compatible, Claude native, and Gemini native subsets are identified as future activation candidates once adapter work is done.
- Provider-specific async families are kept as documentation-backed inventory hints only.

## Billing Posture

- No billing JSON bundle is emitted in this pass.
- The docs expose group multipliers and at least one fixed-price exception, but not a complete per-model price table that can be safely converted into credits.
- The generated billing guide documents the correct pricing rule formula and the gating conditions required before direct billing import.

## Recommended Next Step

1. Import the n1n bundle as staging-only rows so provider/category inventory and source URLs are tracked in the admin system.
2. Add a dedicated n1n provider adapter or generic OpenAI-compatible promotion path if you want selected LLM/Image rows to become runnable.
3. Capture a per-model public pricing source before generating direct billing rows.