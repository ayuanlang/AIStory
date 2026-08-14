# Provider Callback Support Matrix

Date: 2026-03-20

## Scope

This document describes callback support in the current AIStory codebase.

It separates two different callback layers:

1. AIStory async job callback
   - Frontend can send `callback_url` to AIStory `/generate/image/submit` and `/generate/video/submit`.
   - AIStory stores the job locally and dispatches its own completion callback when the job finishes.

2. Upstream provider callback
   - AIStory may or may not forward a callback URL into the upstream provider payload.
   - This is provider-specific and modality-specific.

## Current Summary

| Provider | Image upstream callback | Video upstream callback | Notes |
| --- | --- | --- | --- |
| KIE | Partial | Partial | Only some async families use upstream callback. Image callback is currently required/enabled mainly for `z-image` family. Video callback is enabled for specific async families such as Kling 2.6 i2v and several KIE async adapters that accept `callBackUrl`. |
| GRSAI | Yes | Partial | Image callback now forwards `webHook` when `callback_url` is present; otherwise falls back to `-1`. Video behavior remains endpoint/model dependent and some branches still use polling-first behavior. |
| RunningHub | Yes | Yes | Current standard-model integration now forwards upstream `webhookUrl` for image and video when explicitly configured or when AIStory auto-assigns a public callback URL. Submit-then-query polling remains in place as the fallback completion path. |
| APIYI | No | No upstream callback in current adapter | Current image adapter uses synchronous `/v1/images/generations`. Current video adapter uses submit-and-poll style `/v1/videos` handling. |
| Doubao | No | Yes | Current image path uses synchronous `/images/generations` style submission. Current video path forwards `callback_url` when present. |
| Ark | N/A | Yes | New Seedance 2.0 provider via Ark **API Key** (`Bearer`) + `POST /api/v3/contents/generations/tasks`. Same production callback path as other video APIs. Does **not** use AK/SK. |
| Ark-Seedance | N/A | Yes | Existing native private-asset path (`AK:SK:EP_TOKEN`). Unchanged; separate from provider `ark`. |
| NukoAi | N/A | No (poll-only) | Submit `POST /videos` then poll `GET /videos/{id}`. Adapter ignores pure-callback mode; no upstream webhook. |
| Dubai | OpenAI-compatible `/v1/images/generations` | No (poll-only) | 星耀. Video: `POST /v1/videos` → poll `GET /v1/videos/{id}` → download `/content`. Base URL must not include `/v1`. |

## AIStory Internal Callback Layer

### Image

- Frontend `generateImage(...)` creates a callback ticket for non-local deployments by default.
- Frontend sends `callback_url` to AIStory `/generate/image/submit`.
- Backend stores `callback_url` on the image job.
- Backend dispatches AIStory callback on job completion even if upstream provider never used webhook.

### Video

- Frontend `generateVideo(...)` does the same for `/generate/video/submit`.
- Backend stores `callback_url` on the video job.
- Backend dispatches AIStory callback when the local async job finishes.

This means the frontend may still observe callback-based completion from AIStory even when the upstream provider itself was polled.

## Provider Details

### KIE

- Callback URL is read from `webHook`, `callBackUrl`, `callback_url`, or `callbackUrl`.
- If the deployment looks local, KIE callback may be forced to `-1` and polling is used.
- If the deployment looks public and the model family requires callback, AIStory can auto-assign a callback URL.
- In current code, upstream callback is not universal for all KIE image models. It is primarily wired for async families such as `z-image`.

### GRSAI

- Image path previously hardcoded `webHook: "-1"`.
- Current code now forwards upstream `webHook` when a valid callback URL exists.
- If no valid callback exists, it still falls back to `-1`.
- Result polling remains in place as fallback.

### RunningHub

- Current adapter uses standard-model submit/query endpoints.
- Standard-model request handling now accepts explicit callback configuration via `webhookUrl` and also auto-assigns a public callback URL when deployment hints indicate a public AIStory backend.
- Image and video submit payloads now forward upstream `webhookUrl` when a valid callback URL is available.
- Submit/query polling is still retained as fallback, so callback delivery is an optimization rather than a hard dependency.
- This aligns the adapter with validated RunningHub standard-model protocol evidence showing optional `webhookUrl` support on submit requests.

### APIYI

- Current image adapter supports `/v1/images/generations` only and treats it as text-to-image sync style.
- Current image adapter does not support reference-image async callback flow.
- Current video adapter uses submit-and-poll flow and does not forward upstream callback.

### Doubao

- Current image adapter uses `/images/generations` request path and does not attach callback.
- Current video adapter forwards `callback_url` when present.

### Ark (Seedance 2.0, API Key)

- Video provider key: `ark` (distinct from existing `ark-seedance`).
- Auth per official docs: long-lived **Ark API Key** only (`Authorization: Bearer <API_Key>`). No AK/SK required.
- Upstream: `POST/GET https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`.
- Production callback path identical to other video APIs (`callback_url` → `/api/v1/generate/callback/video-job-{job_id}`; pure-callback when public deploy; compensation + timeout poll fallback).
- Callback/query body: Ark `ContentGenerationTask` (`content.video_url`, `usage.completion_tokens`, `duration` / `ratio` / `resolution` / `framespersecond`).

### Ark-Seedance (existing, unchanged)

- Separate provider `ark-seedance` for private-asset registration (`AK:SK:EP_TOKEN`).
- Not used by the new `ark` Seedance-2 API-Key integration.

### NukoAi

- Video only. Upstream is **poll-only** (`POST /videos` → `GET /videos/{id}`); no upstream webhook.
- AIStory adapter always submits then polls (default interval 3–5s) and **never** returns `pending_callback`, even when global pure-callback mode is enabled.
- Reference images/audio/video must be public `https` URLs (provider downloads them server-side).
- Model / duration / ratio are account-specific; configure `SystemAPISetting.model` from the provider `GET /models` list.

### Dubai (星耀)

- Video: **poll-only**. `POST /v1/videos` → `GET /v1/videos/{id}` until `status=completed` → download `GET /v1/videos/{id}/content` with the same Bearer key.
- SDK `base_url` is the host only (`https://dubai3000.xyz`); `/v1` belongs on the request path.
- JSON refs: `reference_images`, `reference_audio_urls`, `reference_video_urls`. Duration 1–15; aspect `16:9|9:16|1:1`; resolution `480p|720p`.
- Image / LLM: OpenAI-compatible (`POST /v1/images/generations`, `POST /v1/chat/completions`) when admin adds those system API rows. Do not invent model IDs; use `GET /v1/models`.
- Adapter ignores pure-callback mode; no upstream webhook.

## Practical Rule Of Thumb

When debugging callback behavior, check in this order:

1. Did the frontend send `callback_url` to AIStory?
2. Did AIStory local async job store that callback URL?
3. Did the provider adapter forward callback into the upstream payload for that specific provider and modality?
4. If not, is the adapter intentionally polling-only for that path?

## Status As Of This Update

- GRSAI image upstream callback forwarding has been enabled in code.
- RunningHub standard-model image/video upstream callback forwarding is now enabled through `webhookUrl`, with polling fallback preserved.
- NukoAi video is integrated as a hard poll-only provider (no upstream callback).
- Dubai / 星耀 video is integrated as a hard poll-only provider (`/v1/videos` + `/content` download).
- Failure propagation has been improved so moderation-like upstream errors can surface with richer detail, including `failure_reason` when available.