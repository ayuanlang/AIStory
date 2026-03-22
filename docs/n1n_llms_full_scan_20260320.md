# n1n llms.txt Full Scan 2026-03-20

Source: https://docs.n1n.ai/llms.txt

This document is a protocol-level scan of n1n docs derived from llms.txt and supporting pricing/base-url pages.
It intentionally distinguishes documented protocol families from importable model inventory, because n1n llms.txt is primarily a capability index rather than a machine-readable model list.

## Scan Result

- Indexed docs entries: 442
- API Docs entries: 320
- Protocol profiles prepared: 46

## Base URLs

- Primary: https://api.n1n.ai
- Mirror: https://hk.n1n.ai
- Documented endpoint paths: /v1, /v1/chat/completions, /v1/responses

## Category Counts

- Image: 102
- LLM: 90
- Music: 18
- Tools: 1
- Video: 96
- Voice: 13

## Protocol Profiles

- Doubao Image Image: category=Image, style=async_task, docs=11, endpoint=undocumented in base pages
- Fal.ai Image: category=Image, style=async_task, docs=21, endpoint=undocumented in base pages
- FLUX Image: category=Image, style=async_task, docs=4, endpoint=undocumented in base pages
- Gemini Native Image Generation: category=Image, style=native, docs=7, endpoint=/v1beta/models/{model}:generateContent
- GPT Image Image: category=Image, style=async_task, docs=6, endpoint=undocumented in base pages
- Grok Image Image: category=Image, style=async_task, docs=2, endpoint=undocumented in base pages
- Ideogram Image: category=Image, style=async_task, docs=10, endpoint=undocumented in base pages
- Jimeng Image Image: category=Image, style=async_task, docs=2, endpoint=undocumented in base pages
- Kling Platform Image: category=Image, style=async_task, docs=5, endpoint=undocumented in base pages
- Midjourney Image: category=Image, style=async_task, docs=11, endpoint=undocumented in base pages
- Qwen Image Image: category=Image, style=async_task, docs=3, endpoint=undocumented in base pages
- Replicate Platform Image: category=Image, style=async_task, docs=14, endpoint=undocumented in base pages
- Tencent AIGC Image Image: category=Image, style=async_task, docs=2, endpoint=undocumented in base pages
- Claude Chat Compatible: category=LLM, style=chat_compatible, docs=5, endpoint=/v1/chat/completions
- Claude Native Messages: category=LLM, style=native, docs=7, endpoint=/v1/messages
- Fal.ai LLM: category=LLM, style=provider_specific, docs=2, endpoint=undocumented in base pages
- Gemini Native Embeddings: category=LLM, style=native, docs=2, endpoint=/v1beta/models/{model}:embedContent
- Gemini Native Generate Content: category=LLM, style=native, docs=13, endpoint=/v1beta/models/{model}:generateContent
- Kling Platform LLM: category=LLM, style=provider_specific, docs=20, endpoint=undocumented in base pages
- MiniMax Platform LLM: category=LLM, style=provider_specific, docs=3, endpoint=undocumented in base pages
- OpenAI Compatible Chat Completions: category=LLM, style=openai_compatible, docs=17, endpoint=/v1/chat/completions
- OpenAI Compatible Embeddings: category=LLM, style=openai_compatible, docs=1, endpoint=/v1/embeddings
- OpenAI Compatible Responses: category=LLM, style=openai_compatible, docs=7, endpoint=/v1/responses
- Replicate Platform LLM: category=LLM, style=provider_specific, docs=15, endpoint=undocumented in base pages
- Suno Music Music: category=Music, style=async_task, docs=18, endpoint=undocumented in base pages
- Rerank Tools: category=Tools, style=provider_specific, docs=1, endpoint=undocumented in base pages
- Doubao Video Video: category=Video, style=async_task, docs=9, endpoint=undocumented in base pages
- Fal.ai Video: category=Video, style=async_task, docs=8, endpoint=undocumented in base pages
- Grok Video Video: category=Video, style=async_task, docs=2, endpoint=undocumented in base pages
- Hailuo Video Video: category=Video, style=async_task, docs=4, endpoint=undocumented in base pages
- Jimeng Video Video: category=Video, style=async_task, docs=4, endpoint=undocumented in base pages
- Kling Platform Video: category=Video, style=async_task, docs=20, endpoint=undocumented in base pages
- Luma Video Video: category=Video, style=async_task, docs=4, endpoint=undocumented in base pages
- MiniMax Platform Video: category=Video, style=async_task, docs=4, endpoint=undocumented in base pages
- Replicate Platform Video: category=Video, style=async_task, docs=2, endpoint=undocumented in base pages
- Runway Video Video: category=Video, style=async_task, docs=2, endpoint=undocumented in base pages
- Sora Video Video: category=Video, style=async_task, docs=16, endpoint=undocumented in base pages
- Tencent AIGC Video Video: category=Video, style=async_task, docs=3, endpoint=undocumented in base pages
- Tongyi Video Video: category=Video, style=async_task, docs=2, endpoint=undocumented in base pages
- Veo Video Video: category=Video, style=async_task, docs=7, endpoint=undocumented in base pages
- Vidu Platform Video: category=Video, style=async_task, docs=8, endpoint=undocumented in base pages
- Kling Platform Voice: category=Voice, style=async_task, docs=1, endpoint=undocumented in base pages
- MiniMax Platform Voice: category=Voice, style=async_task, docs=5, endpoint=undocumented in base pages
- OpenAI Compatible Audio Chat: category=Voice, style=openai_compatible, docs=2, endpoint=/v1/chat/completions
- OpenAI Compatible Text To Speech: category=Voice, style=openai_compatible, docs=1, endpoint=/v1/audio/speech
- OpenAI Compatible Audio Transcriptions: category=Voice, style=openai_compatible, docs=2, endpoint=/v1/audio/transcriptions

## Import Guidance

- Safe default: import n1n as staging-only protocol rows, not as active model inventory.
- The docs clearly publish base URLs, protocol families, and group-based pricing logic, but they do not expose a complete machine-readable per-model price table.
- Direct billing import should stay blocked until model-level official baselines are sourced, or until a separate public price table is captured.
- OpenAI-compatible, Claude native, and Gemini native subsets are the most suitable future runtime activation candidates once a provider adapter is added.