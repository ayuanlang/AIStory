# KIE Model Alias Map

This table documents legacy/internal names mapped to KIE canonical model names used for Market APIs.

| Legacy / Short Name | Canonical Model |
|---|---|
| `kling3`, `kling-3.0`, `kling-3-0` | `kling-3.0/video` |
| `kling/2.6-text-to-video` | `kling-2.6/text-to-video` |
| `kling/2.6-image-to-video` | `kling-2.6/image-to-video` |
| `kling/2.6-motion-control` | `kling-2.6/motion-control` |
| `kling/v25-turbo-text-to-video-pro` | `kling/v2-5-turbo-text-to-video-pro` |
| `kling/v25-turbo-image-to-video-pro` | `kling/v2-5-turbo-image-to-video-pro` |
| `klingv2.1` | `kling-v2.1` |
| `klingv2.5` | `kling-v2.5` |
| `grok-imagine` | `grok-imagine/text-to-image` |
| `grok-imagine-video` | `grok-imagine/text-to-video` |
| `qwen-image` | `qwen/text-to-image` |
| `imagen4-fast` | `google/imagen4-fast` |
| `imagen4-ultra` | `google/imagen4-ultra` |
| `imagen4` | `google/imagen4` |
| `nano-banana` | `google/nano-banana` |
| `nano-banana-edit` | `google/nano-banana-edit` |
| `nanobanana2` | `google/nanobanana2` |
| `seedream4.5` | `seedream/4.5-text-to-image` |
| `seedream4.5-edit` | `seedream/4.5-edit` |
| `flux2-pro` | `flux-2/pro-text-to-image` |
| `flux2-pro-i2i` | `flux-2/pro-image-to-image` |
| `flux2-flex` | `flux-2/flex-text-to-image` |
| `flux2-flex-i2i` | `flux-2/flex-image-to-image` |
| `gpt-image-1.5` | `gpt-image/1-5-text-to-image` |
| `gpt-image-1.5-i2i` | `gpt-image/1-5-image-to-image` |
| `sora2`, `sora2-t2v` | `sora-2-text-to-video` |
| `sora2-i2v` | `sora-2-image-to-video` |
| `sora2-pro` | `sora-2-pro-text-to-video` |
| `sora2-pro-i2v` | `sora-2-pro-image-to-video` |
| `bytedance-v1-pro` | `bytedance/v1-pro-text-to-video` |
| `bytedance-v1-pro-i2v` | `bytedance/v1-pro-image-to-video` |
| `bytedance-v1-pro-fast-i2v` | `bytedance/v1-pro-fast-image-to-video` |
| `bytedance-v1-lite` | `bytedance/v1-lite-text-to-video` |
| `bytedance-v1-lite-i2v` | `bytedance/v1-lite-image-to-video` |
| `hailuo` | `hailuo/02-text-to-video-pro` |
| `hailuo-pro-i2v` | `hailuo/02-image-to-video-pro` |
| `hailuo-standard` | `hailuo/02-text-to-video-standard` |
| `hailuo-standard-i2v` | `hailuo/02-image-to-video-standard` |
| `hailuo-2.3-pro` | `hailuo/2-3-image-to-video-pro` |
| `hailuo-2.3-standard` | `hailuo/2-3-image-to-video-standard` |
| `wan-turbo` | `wan/2-6-text-to-video` |
| `wan-i2v` | `wan/2-6-image-to-video` |
| `wan-v2v` | `wan/2-6-video-to-video` |
| `wan-a14b-t2v` | `wan/2-2-a14b-text-to-video-turbo` |
| `wan-a14b-i2v` | `wan/2-2-a14b-image-to-video-turbo` |
| `wan-a14b-s2v` | `wan/2-2-a14b-speech-to-video-turbo` |
| `wan-flash-i2v` | `wan/2-6-flash-image-to-video` |
| `wan-flash-v2v` | `wan/2-6-flash-video-to-video` |
| `veo3-fast`, `veo-3-fast` | `veo3_fast` |
| `veo3`, `veo-3`, `veo`, `veo3.1`, `veo-3.1` | `veo3` |

## LLM Model Names

| Legacy / Short Name | Canonical Model |
|---|---|
| `claude-opus-4.5` | `claude-opus-4-5` |
| `claude-sonnet-4.5` | `claude-sonnet-4-5` |

Note: `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-pro`, `gpt-5-2` use dots and are correct as-is.

## Image Model Name Fixes

| Old Name | Correct Name | Status |
|---|---|---|
| `gpt-image/1-5-text-to-image` | `gpt-image/1.5-text-to-image` | Fixed (dot, not hyphen) |
| `gpt-image/1-5-image-to-image` | `gpt-image/1.5-image-to-image` | Fixed (dot, not hyphen) |
| `google/nanobanana2` | — | Retired by KIE |
| `google/pro-image-to-image` | — | Retired by KIE |
| `z-image-v4.0` | — | Retired by KIE |
| `z-image-v4.5` | — | Retired by KIE |
| `elevenlabs` (bare) | — | Retired; use sub-models like `elevenlabs/text-to-dialogue-v3` |

## Notes

- Canonical names are used when submitting Market tasks to `POST /api/v1/jobs/createTask`.
- Veo series remains routed via dedicated Veo endpoints in runtime logic.
- Runway, gpt4o-image, flux/kontext, suno use dedicated API routes (not Market API).
- Legacy names remain accepted by runtime mapping for backward compatibility.

## Ambiguity Adjudication (2026-03-06)

This section records how ambiguous or internally inconsistent doc entries were adjudicated during strict enum verification.

### Decision Rules

1. Prefer endpoint-local `model` enum `Value/Default/Example` when they are internally consistent.
2. If an English page is internally inconsistent, cross-check the corresponding Chinese page under `/cn/`.
3. If conflict remains, prefer values that are consistent with:
	 - page path semantics,
	 - neighboring model pages in the same family,
	 - existing unified Market request shape.
4. Preserve backward compatibility by adding alias remaps instead of hard-breaking old names.

### Adjudicated Items

- Kling 2.5 Turbo I2V Pro:
	- Canonical: `kling/v2-5-turbo-image-to-video-pro`
	- Legacy kept as alias: `kling/v25-turbo-image-to-video-pro`
	- Rationale: `/cn/market/kling/v25-turbo-image-to-video-pro` explicitly declares `kling/v2-5-turbo-image-to-video-pro`; one English page variant showed a conflicting value inconsistent with path/topic.

- Kling 2.6 Motion Control:
	- Canonical: `kling-2.6/motion-control`
	- Legacy kept as alias: `kling/2.6-motion-control`
	- Rationale: endpoint enum and request example consistently use hyphenated family prefix format.

### Source Snapshot

- Sitemap inventory used to enumerate target pages: `https://docs.kie.ai/sitemap.xml`
- Cross-check pages:
	- `https://docs.kie.ai/market/kling/v25-turbo-image-to-video-pro`
	- `https://docs.kie.ai/cn/market/kling/v25-turbo-image-to-video-pro`
	- `https://docs.kie.ai/market/kling/motion-control`
	- `https://docs.kie.ai/cn/market/kling/motion-control`
