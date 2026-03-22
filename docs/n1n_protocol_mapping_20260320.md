# n1n API Mapping 2026-03-20

This mapping normalizes n1n protocol families into internal provider/category rows. Because n1n llms.txt is a protocol index rather than a clean model inventory, these rows are synthetic staging entries intended for later adapter work.

## Base URLs

- Primary: https://api.n1n.ai
- Mirror: https://hk.n1n.ai

## Canonical Mapping

- doubao_image_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=i2i,t2i, input_formats=text,image, billing_unit_type=per_call
- fal_ai_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i,i2i, input_formats=text,image, billing_unit_type=per_call
- flux_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i,i2i, input_formats=text,image, billing_unit_type=per_call
- gemini_native_image: category=Image, style=native, endpoint_hint=/v1beta/models/{model}:generateContent, generation_modes=t2i,i2i, input_formats=text,image, billing_unit_type=per_call
- gpt_image_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i,i2i, input_formats=text,image, billing_unit_type=per_call
- grok_image_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i,i2i, input_formats=text,image, billing_unit_type=per_call
- ideogram_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i,i2i,i2t, input_formats=text,image, billing_unit_type=per_call
- jimeng_image_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i,i2i, input_formats=text,image, billing_unit_type=per_call
- kling_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_call
- midjourney_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=i2t, input_formats=text, billing_unit_type=per_call
- qwen_image_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=i2i, input_formats=text,image, billing_unit_type=per_call
- replicate_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i, input_formats=text, billing_unit_type=per_call
- tencent_image_image: category=Image, style=async_task, endpoint_hint=undocumented, generation_modes=t2i, input_formats=text, billing_unit_type=per_call
- claude_chat_compatible: category=LLM, style=chat_compatible, endpoint_hint=/v1/chat/completions, generation_modes=n/a, input_formats=text,image, billing_unit_type=per_million_tokens
- claude_native_messages: category=LLM, style=native, endpoint_hint=/v1/messages, generation_modes=n/a, input_formats=text,pdf,web, billing_unit_type=per_million_tokens
- fal_ai_llm: category=LLM, style=provider_specific, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- gemini_native_embeddings: category=LLM, style=native, endpoint_hint=/v1beta/models/{model}:embedContent, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- gemini_native_generate_content: category=LLM, style=native, endpoint_hint=/v1beta/models/{model}:generateContent, generation_modes=t2a, input_formats=text, billing_unit_type=per_million_tokens
- kling_llm: category=LLM, style=provider_specific, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- minimax_llm: category=LLM, style=provider_specific, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- openai_chat_completions: category=LLM, style=openai_compatible, endpoint_hint=/v1/chat/completions, generation_modes=n/a, input_formats=text,image,web, billing_unit_type=per_million_tokens
- openai_embeddings: category=LLM, style=openai_compatible, endpoint_hint=/v1/embeddings, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- openai_responses: category=LLM, style=openai_compatible, endpoint_hint=/v1/responses, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- replicate_llm: category=LLM, style=provider_specific, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- suno_music: category=Music, style=async_task, endpoint_hint=undocumented, generation_modes=t2a, input_formats=text, billing_unit_type=per_call
- rerank_tools: category=Tools, style=provider_specific, endpoint_hint=undocumented, generation_modes=n/a, input_formats=n/a, billing_unit_type=per_call
- doubao_video_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=t2v,i2v, input_formats=text,image, billing_unit_type=per_second
- fal_ai_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=i2v,t2v, input_formats=text,image, billing_unit_type=per_second
- grok_video_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=t2v, input_formats=text, billing_unit_type=per_second
- hailuo_video_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=i2v, input_formats=text,image, billing_unit_type=per_second
- jimeng_video_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=t2v, input_formats=text, billing_unit_type=per_second
- kling_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=t2v,i2v,v2v, input_formats=text,image,video, billing_unit_type=per_second
- luma_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=v2v, input_formats=text,video, billing_unit_type=per_second
- minimax_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=i2v, input_formats=image,text, billing_unit_type=per_second
- replicate_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_second
- runway_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=n/a, input_formats=image,text, billing_unit_type=per_second
- sora_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=i2v,t2v,v2v, input_formats=text,image,video, billing_unit_type=per_second
- tencent_video_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_second
- tongyi_video_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=n/a, input_formats=text, billing_unit_type=per_second
- veo_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=t2v,i2v, input_formats=text,image, billing_unit_type=per_second
- vidu_video: category=Video, style=async_task, endpoint_hint=undocumented, generation_modes=t2v,i2v, input_formats=text,image, billing_unit_type=per_second
- kling_voice: category=Voice, style=async_task, endpoint_hint=undocumented, generation_modes=t2a, input_formats=text, billing_unit_type=per_call
- minimax_voice: category=Voice, style=async_task, endpoint_hint=undocumented, generation_modes=t2a,a2a, input_formats=text, billing_unit_type=per_call
- openai_audio_chat_completions: category=Voice, style=openai_compatible, endpoint_hint=/v1/chat/completions, generation_modes=n/a, input_formats=text, billing_unit_type=per_million_tokens
- openai_audio_speech: category=Voice, style=openai_compatible, endpoint_hint=/v1/audio/speech, generation_modes=t2a, input_formats=text, billing_unit_type=per_call
- openai_audio_transcriptions: category=Voice, style=openai_compatible, endpoint_hint=/v1/audio/transcriptions, generation_modes=a2t, input_formats=audio, billing_unit_type=per_call

## Mapping Notes

- OpenAI-compatible chat, responses, embeddings, images, and audio families are mapped to explicit endpoint hints because the base docs publish those paths.
- Claude native and Gemini native rows are mapped as protocol families, not model inventory rows.
- Provider-specific async families such as Midjourney, Kling, Vidu, Suno, Runway, and Luma remain endpoint-undocumented staging rows until detail pages are captured more systematically.
- All n1n rows are imported as deprecated/inactive staging rows in this bundle.