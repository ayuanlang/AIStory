import re
import uuid
import json
import asyncio
import logging
import requests
import urllib.parse
import base64
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

def _debug_log(msg):
    logger.debug(msg)

def _strip_base64_from_log(payload):
    try:
        s = str(payload)
        if len(s) > 200:
            return s[:200] + '... [truncated]'
        return s
    except Exception:
        return ""

class ZlhubMixin:
    async def _handle_zlhub_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        if gen_type != "video":
            return {"error": "zlhub generation type not supported yet", "submit_failed": True}

        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": "No zlhub API Key", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        provider_name = self._vendor_label(config.get("provider") or tool_conf.get("provider") or "zlhub")
        base_url = str(config.get("base_url") or "https://zlhub.xiaowaiyou.cn/zhonglian/api/v1").strip().rstrip("/")
        raw_endpoint = str(tool_conf.get("endpoint") or "").strip()
        endpoint = raw_endpoint or "/proxy/ark/contents/generations/tasks"
        raw_query_endpoint = self._normalize_zlhub_task_query_endpoint(
            tool_conf.get("query_endpoint") or tool_conf.get("queryEndpoint")
        )
        model = str(config.get("model") or "doubao-seedance-2-0").strip()
        model_lower = str(model or "").strip().lower()
        is_seedance2 = model_lower.startswith("doubao-seedance-2")
        zlhub_trace_id = f"zlhub-{uuid.uuid4().hex[:10]}"
        if re.match(r"^https?://", endpoint, flags=re.IGNORECASE):
            if "/proxy/chat/completions" in endpoint.lower():
                submit_url = re.sub(r"/proxy/chat/completions/?$", "/proxy/ark/contents/generations/tasks", endpoint, flags=re.IGNORECASE)
            elif "/api/v3" in endpoint.lower() or endpoint.lower().endswith("/contents/generations/tasks"):
                submit_url = self._normalize_doubao_video_tasks_endpoint(endpoint)
            else:
                submit_url = endpoint.rstrip("/")
        elif raw_endpoint:
            normalized_relative_endpoint = endpoint
            if "/proxy/chat/completions" in normalized_relative_endpoint.lower():
                normalized_relative_endpoint = re.sub(r"/proxy/chat/completions/?$", "/proxy/ark/contents/generations/tasks", normalized_relative_endpoint, flags=re.IGNORECASE)
            submit_url = f"{base_url}{normalized_relative_endpoint if normalized_relative_endpoint.startswith('/') else '/' + normalized_relative_endpoint}"
        elif "/api/v3" in base_url.lower() or base_url.lower().endswith("/contents/generations/tasks"):
            submit_url = self._normalize_doubao_video_tasks_endpoint(base_url)
        else:
            submit_url = self._normalize_zlhub_task_query_endpoint(base_url)

        explicit_query_endpoint = str(tool_conf.get("query_endpoint") or tool_conf.get("queryEndpoint") or "").strip()
        if re.match(r"^https?://", raw_query_endpoint, flags=re.IGNORECASE):
            if "/api/v3" in raw_query_endpoint.lower() or raw_query_endpoint.lower().endswith("/contents/generations/tasks"):
                query_endpoint = self._normalize_doubao_video_tasks_endpoint(raw_query_endpoint)
            else:
                query_endpoint = raw_query_endpoint.rstrip("/")
        elif not explicit_query_endpoint:
            query_endpoint = submit_url
        elif "/api/v3" in base_url.lower() or base_url.lower().endswith("/contents/generations/tasks"):
            query_endpoint = self._normalize_doubao_video_tasks_endpoint(f"{base_url}/{raw_query_endpoint.lstrip('/')}" if not raw_query_endpoint.startswith("http") else raw_query_endpoint)
        else:
            query_endpoint = f"{base_url}{raw_query_endpoint if raw_query_endpoint.startswith('/') else '/' + raw_query_endpoint}"

        prompt_text = self._merge_negative_prompt(prompt, negative_prompt)

        if is_seedance2:
            logger.info(
                "[ZLHubSeedance2] request_init | trace_id=%s gen_type=%s provider=%s model=%s submit_url=%s query_endpoint=%s duration_in=%s aspect_ratio_in=%s",
                zlhub_trace_id,
                gen_type,
                provider_name,
                model,
                submit_url,
                query_endpoint,
                duration,
                aspect_ratio,
            )

        raw_image_refs = ref_image if isinstance(ref_image, list) else [ref_image]
        resolved_image_refs: List[str] = []
        for item in raw_image_refs:
            text = str(item or "").strip()
            if not text:
                continue
            resolved = await self._resolve_ref_for_api_async(
                text,
                force_data_uri_for_local=True,
                prefer_public_upload_url=True,
            )
            if resolved:
                resolved_image_refs.append(str(resolved).strip())
        resolved_image_refs = [item for item in dict.fromkeys(resolved_image_refs) if item]

        resolved_last_frame = None
        if str(last_frame_url or "").strip():
            resolved_last_frame = await self._resolve_ref_for_api_async(
                last_frame_url,
                force_data_uri_for_local=True,
                prefer_public_upload_url=True,
            )
            resolved_last_frame = str(resolved_last_frame or "").strip() or None

        reference_video_urls = self._resolve_public_media_urls(
            tool_conf.get("reference_video_urls") or tool_conf.get("ref_video_urls") or []
        )
        reference_audio_urls = self._resolve_public_media_urls(
            tool_conf.get("reference_audio_urls") or tool_conf.get("ref_audio_urls") or []
        )

        dropped_mixed_reference_counts = {
            "image": 0,
            "video": 0,
            "audio": 0,
        }

        seedance2_ref_mode = ""
        seedance2_payload_mode = ""
        if is_seedance2:
            raw_ref_mode = str(
                tool_conf.get("ref_mode")
                or tool_conf.get("video_ref_mode")
                or tool_conf.get("video_mode")
                or tool_conf.get("video_mode_unified")
                or ""
            ).strip().lower()

            if raw_ref_mode in {"refs_video", "entity_refs", "reference", "reference_images", "reference_image"}:
                seedance2_ref_mode = "entity_refs"
            elif raw_ref_mode in {"start_end", "start-end", "start+end", "first_last", "first_last_frame", "first_and_last"}:
                seedance2_ref_mode = "start_end"
            elif raw_ref_mode in {"end", "last", "last_frame"}:
                seedance2_ref_mode = "end"
            elif raw_ref_mode in {"start", "first", "first_frame", "auto"}:
                seedance2_ref_mode = "start"

            if not seedance2_ref_mode:
                if resolved_last_frame:
                    seedance2_ref_mode = "start_end"
                elif len(resolved_image_refs) > 1 or reference_video_urls or reference_audio_urls:
                    seedance2_ref_mode = "entity_refs"
                elif resolved_image_refs:
                    seedance2_ref_mode = "start"
                else:
                    seedance2_ref_mode = "start"

            seedance2_payload_mode = "reference_media" if seedance2_ref_mode == "entity_refs" else "frame_content"

        # Seedance-2 rejects payloads that mix first/last frame content with
        # additional reference media roles in the same request content.
        if is_seedance2 and (resolved_image_refs or resolved_last_frame or reference_video_urls or reference_audio_urls):
            if seedance2_payload_mode == "frame_content":
                keep_first_ref = str(resolved_image_refs[0] or "").strip() if resolved_image_refs else ""
                dropped_mixed_reference_counts["image"] = max(0, len(resolved_image_refs) - (1 if keep_first_ref else 0))
                dropped_mixed_reference_counts["video"] = len(reference_video_urls)
                dropped_mixed_reference_counts["audio"] = len(reference_audio_urls)

                resolved_image_refs = [keep_first_ref] if keep_first_ref else []
                reference_video_urls = []
                reference_audio_urls = []
            else:
                dropped_last_frame = 1 if bool(resolved_last_frame) else 0
                resolved_last_frame = None
                if dropped_last_frame:
                    logger.info(
                        "[ZLHubSeedance2] dropped last_frame in reference_media mode | trace_id=%s",
                        zlhub_trace_id,
                    )

            if any(dropped_mixed_reference_counts.values()):
                logger.info(
                    "[ZLHubSeedance2] dropped mixed reference media | trace_id=%s ref_mode=%s payload_mode=%s dropped_image_refs=%s dropped_video_refs=%s dropped_audio_refs=%s",
                    zlhub_trace_id,
                    seedance2_ref_mode or "start",
                    seedance2_payload_mode or "frame_content",
                    dropped_mixed_reference_counts["image"],
                    dropped_mixed_reference_counts["video"],
                    dropped_mixed_reference_counts["audio"],
                )

        if is_seedance2:
            logger.info(
                "[ZLHubSeedance2] refs_resolved | trace_id=%s ref_mode=%s payload_mode=%s image_refs=%s has_last_frame=%s ref_videos=%s ref_audios=%s",
                zlhub_trace_id,
                seedance2_ref_mode or "start",
                seedance2_payload_mode or "frame_content",
                len(resolved_image_refs),
                bool(resolved_last_frame),
                len(reference_video_urls),
                len(reference_audio_urls),
            )

        moderation_results: List[Dict[str, Any]] = []
        moderation_candidates: List[tuple[str, str]] = []
        if resolved_image_refs:
            if len(resolved_image_refs) == 1 and not resolved_last_frame:
                moderation_candidates.append((resolved_image_refs[0], "first_frame"))
            else:
                for idx, item in enumerate(resolved_image_refs):
                    moderation_candidates.append((item, "first_frame" if idx == 0 else "reference_image"))
        if resolved_last_frame:
            moderation_candidates.append((resolved_last_frame, "last_frame"))

        moderated_first_and_refs: List[str] = []
        moderated_last_frame = resolved_last_frame
        if moderation_candidates:
            candidate_refs = [item[0] for item in moderation_candidates]
            candidate_roles = [item[1] for item in moderation_candidates]
            batch_result = await self._maybe_moderate_zlhub_images(candidate_refs, config, candidate_roles)
            if batch_result.get("error") and batch_result.get("submit_failed"):
                return {
                    "error": batch_result.get("error"),
                    "details": batch_result.get("details") or batch_result,
                    "submit_failed": True,
                }

            moderation_results = list(batch_result.get("items") or [])
            for idx, moderation_result in enumerate(moderation_results):
                candidate_ref, role = moderation_candidates[idx] if idx < len(moderation_candidates) else ("", "")
                if moderation_result.get("blocked"):
                    return {
                        "error": f"{provider_name} moderation blocked reference material",
                        "details": moderation_result,
                        "submit_failed": True,
                    }
                approved_ref = str(moderation_result.get("approved_ref") or candidate_ref or "").strip()
                if role == "last_frame":
                    moderated_last_frame = approved_ref or moderated_last_frame
                elif approved_ref:
                    moderated_first_and_refs.append(approved_ref)

        if moderated_first_and_refs:
            resolved_image_refs = [item for item in dict.fromkeys(moderated_first_and_refs) if item]
        if moderated_last_frame:
            resolved_last_frame = moderated_last_frame

        is_i2v_request = bool(resolved_image_refs or resolved_last_frame)

        content_payload: List[Dict[str, Any]] = []
        if prompt_text:
            content_payload.append({"type": "text", "text": prompt_text})

        if resolved_image_refs:
            if is_seedance2 and seedance2_payload_mode == "reference_media":
                for item in resolved_image_refs:
                    content_payload.append({
                        "type": "image_url",
                        "image_url": {"url": item},
                        "role": "reference_image",
                    })
            elif len(resolved_image_refs) == 1 and not resolved_last_frame:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": resolved_image_refs[0]},
                    "role": "first_frame",
                })
            else:
                for idx, item in enumerate(resolved_image_refs):
                    content_payload.append({
                        "type": "image_url",
                        "image_url": {"url": item},
                        "role": "first_frame" if idx == 0 else "reference_image",
                    })
        if resolved_last_frame:
            content_payload.append({
                "type": "image_url",
                "image_url": {"url": resolved_last_frame},
                "role": "last_frame",
            })
        for item in reference_video_urls:
            content_payload.append({
                "type": "video_url",
                "video_url": {"url": item},
                "role": "reference_video",
            })
        for item in reference_audio_urls:
            content_payload.append({
                "type": "audio_url",
                "audio_url": {"url": item},
                "role": "reference_audio",
            })

        payload: Dict[str, Any] = {
            "model": model,
            "content": content_payload,
        }

        normalized_ratio = self._normalize_aspect_ratio_value(aspect_ratio)
        if normalized_ratio:
            payload["ratio"] = normalized_ratio

        try:
            payload["duration"] = int(duration or tool_conf.get("duration") or 5)
        except Exception:
            payload["duration"] = 5

        for source_key, target_key in (("resolution", "resolution"), ("generate_audio", "generate_audio")):
            value = tool_conf.get(source_key)
            if value is None:
                continue
            if source_key == "resolution" and is_seedance2 and is_i2v_request:
                logger.info(
                    "[ZLHubSeedance2] dropping unsupported i2v resolution | trace_id=%s model=%s resolution=%s",
                    zlhub_trace_id,
                    model,
                    value,
                )
                continue
            payload[target_key] = value

        raw_tools = tool_conf.get("tools")
        if raw_tools is None and tool_conf.get("web_search"):
            raw_tools = ["web_search"]
        if isinstance(raw_tools, str):
            raw_tools = [raw_tools]
        if isinstance(raw_tools, list):
            normalized_tools: List[Dict[str, Any]] = []
            for item in raw_tools:
                if isinstance(item, dict) and item.get("type"):
                    normalized_tools.append(item)
                    continue
                name = str(item or "").strip().lower()
                if name == "web_search":
                    normalized_tools.append({"type": "web_search"})
            if normalized_tools:
                payload["tools"] = normalized_tools

        base_metadata = {
            "provider": "zlhub",
            "provider_label": provider_name,
            "model": model,
            "prompt": prompt,
            "trace_id": zlhub_trace_id,
            "submit_url": submit_url,
            "query_endpoint": query_endpoint,
            "requested_duration": payload.get("duration"),
            "requested_aspect_ratio": payload.get("ratio"),
            "resolved_reference_count": len(resolved_image_refs),
            "resolved_reference_video_count": len(reference_video_urls),
            "resolved_reference_audio_count": len(reference_audio_urls),
            "resolved_ref_mode": seedance2_ref_mode or None,
            "seedance2_payload_mode": seedance2_payload_mode or None,
            "dropped_mixed_reference_counts": dropped_mixed_reference_counts,
            "moderation": moderation_results,
        }
        if is_seedance2:
            logger.info(
                "[ZLHubSeedance2] submit_ready | trace_id=%s payload_duration=%s payload_ratio=%s tools=%s content_items=%s",
                zlhub_trace_id,
                payload.get("duration"),
                payload.get("ratio"),
                len(payload.get("tools") or []) if isinstance(payload.get("tools"), list) else 0,
                len(content_payload),
            )
        return await self._submit_and_poll_zlhub_video(
            submit_url,
            query_endpoint,
            payload,
            api_key,
            "zlhub_video",
            extra_metadata=base_metadata,
        )

    def _resolve_apiyi_chat_video_model(self, model: str, aspect_ratio: Optional[str] = None, duration: Optional[int] = None) -> str:
        normalized_model = str(model or "").strip() or "sora_video2"
        normalized_ratio = self._normalize_aspect_ratio_value(aspect_ratio)
        try:
            duration_value = int(duration or 0)
        except Exception:
            duration_value = 0

        if normalized_model == "sora-2-pro":
            return normalized_model

        known_reverse = {
            "sora_video2",
            "sora_video2-15s",
            "sora_video2-landscape",
            "sora_video2-landscape-15s",
        }
        if normalized_model not in known_reverse:
            return normalized_model

        wants_landscape = normalized_ratio == "16:9" or "landscape" in normalized_model
        wants_15s = duration_value >= 15 or normalized_model.endswith("-15s")

        resolved_model = "sora_video2-landscape" if wants_landscape else "sora_video2"
        if wants_15s:
            resolved_model = f"{resolved_model}-15s"
        return resolved_model

    def _apiyi_chat_video_size_for_model(self, model: str) -> Optional[str]:
        normalized_model = str(model or "").strip().lower()
        size_map = {
            "sora_video2": "720x1280",
            "sora_video2-15s": "720x1280",
            "sora_video2-landscape": "1280x720",
            "sora_video2-landscape-15s": "1280x720",
            "sora-2-pro": "1024x1792",
        }
        return size_map.get(normalized_model)

    def _extract_apiyi_sse_video_url(self, message_text: str) -> Optional[str]:
        raw = str(message_text or "").strip()
        if not raw:
            return None
        markdown_match = re.search(r"\((https?://[^)\s]+)\)", raw, flags=re.IGNORECASE)
        if markdown_match:
            return markdown_match.group(1)
        url_match = re.search(r"https?://\S+", raw, flags=re.IGNORECASE)
        if url_match:
            return url_match.group(0).rstrip(")].,!?\"'")
        return None

    async def _submit_apiyi_chat_video_stream(self, url, payload, api_key, log_tag, extra_metadata=None):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        _debug_log(f"[{log_tag}] Streaming submit to URL: {url} | Payload: {_strip_base64_from_log(payload)}")

        def _post(use_proxy=True, connection_close: bool = False):
            request_headers = dict(headers)
            if connection_close:
                request_headers["Connection"] = "close"
            kwargs = {
                "json": payload,
                "headers": request_headers,
                "timeout": (60, 360),
                "verify": False,
                "stream": True,
            }
            if not use_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        try:
            try:
                resp = await asyncio.to_thread(_post, True, False)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                try:
                    resp = await asyncio.to_thread(_post, False, False)
                except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    resp = await asyncio.to_thread(_post, False, True)

            if resp.status_code != 200:
                body = ""
                try:
                    body = resp.text
                except Exception:
                    body = ""
                return {"error": f"Submission Failed {resp.status_code}", "details": body[:1000], "submit_failed": True}

            def _consume_stream() -> Dict[str, Any]:
                last_messages: List[str] = []
                progress_value: Optional[float] = None
                video_url: Optional[str] = None
                event_data_lines: List[str] = []

                def _flush_event() -> Optional[str]:
                    nonlocal progress_value, video_url, event_data_lines
                    if not event_data_lines:
                        return None
                    raw_event = "\n".join(event_data_lines).strip()
                    event_data_lines = []
                    if not raw_event:
                        return None
                    if raw_event == "[DONE]":
                        return "done"
                    try:
                        payload_obj = json.loads(raw_event)
                    except Exception:
                        return None
                    choices = payload_obj.get("choices") if isinstance(payload_obj, dict) else None
                    if not isinstance(choices, list) or not choices:
                        return None
                    delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                    content = ""
                    if isinstance(delta, dict):
                        content = str(delta.get("content") or "")
                    if not content:
                        return None
                    content = content.strip()
                    if content:
                        last_messages.append(content)
                        if len(last_messages) > 12:
                            last_messages.pop(0)
                        progress_match = re.search(r"(\d+(?:\.\d+)?)%", content)
                        if progress_match:
                            try:
                                progress_value = float(progress_match.group(1))
                            except Exception:
                                pass
                        extracted_url = self._extract_apiyi_sse_video_url(content)
                        if extracted_url:
                            video_url = extracted_url
                    return None

                for raw_line in resp.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue
                    line = str(raw_line)
                    if not line.strip():
                        signal = _flush_event()
                        if signal == "done":
                            break
                        continue
                    if not line.startswith("data:"):
                        continue
                    event_data_lines.append(line[5:].strip())

                signal = _flush_event()
                if signal == "done":
                    pass
                return {
                    "video_url": video_url,
                    "progress": progress_value,
                    "messages": last_messages,
                }

            stream_result = await asyncio.to_thread(_consume_stream)
            video_url = str((stream_result or {}).get("video_url") or "").strip()
            if not video_url:
                return {
                    "error": "Generation completed without video URL",
                    "details": " | ".join((stream_result or {}).get("messages") or [])[:1000],
                    "submit_failed": True,
                }

            metadata = {
                "apiyi_stream_messages": (stream_result or {}).get("messages") or [],
                "progress": (stream_result or {}).get("progress"),
            }
            if extra_metadata:
                metadata.update(extra_metadata)
            return {"url": video_url, "metadata": metadata}
        except requests.exceptions.Timeout as e:
            return {"error": "Upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            return {"error": "Upstream request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            return {"error": str(e), "submit_failed": True}

    async def _handle_n1n_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        provider_name = self._vendor_label(config.get("provider") or ((config.get("config") or {}).get("provider")) or "n1n")
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": f"No {provider_name} API Key", "submit_failed": True}

        if gen_type != "image":
            return {"error": f"{provider_name} generation type not supported yet: {gen_type}", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        base_url = str(config.get("base_url") or "https://api.n1n.ai").strip().rstrip("/")
        endpoint = str(tool_conf.get("endpoint") or tool_conf.get("endpoint_hint") or "").strip()
        model = str(config.get("model") or "").strip()
        if not endpoint:
            endpoint = "/models/{model}:generateContent" if "v1beta" in base_url or "v1" in base_url else "/v1beta/models/{model}:generateContent"
        if not model:
            return {"error": f"{provider_name} runtime model missing from system configuration", "submit_failed": True}

        endpoint_lower = endpoint.lower()
        if "generatecontent" not in endpoint_lower:
            return {"error": f"{provider_name} image endpoint family not supported yet: {endpoint}", "submit_failed": True}

        resolved_endpoint = endpoint.replace("{model}", urllib.parse.quote(model, safe="-._~"))
        submit_url = resolved_endpoint if re.match(r"^https?://", resolved_endpoint, flags=re.IGNORECASE) else f"{base_url}{resolved_endpoint if resolved_endpoint.startswith('/') else '/' + resolved_endpoint}"

        prompt_text = self._merge_negative_prompt(prompt, negative_prompt)
        parts: List[Dict[str, Any]] = []
        if prompt_text:
            parts.append({"text": prompt_text})

        reference_values = ref_image if isinstance(ref_image, list) else [ref_image]
        for ref_item in reference_values:
            if ref_item is None:
                continue
            if isinstance(ref_item, str) and not ref_item.strip():
                continue
            data_uri = await self._get_image_base64_for_api_async(ref_item, force_data_uri=True)
            if not isinstance(data_uri, str) or not data_uri.startswith("data:image/"):
                return {"error": f"{provider_name} Gemini image editing requires resolvable image inputs", "submit_failed": True}
            marker = ";base64,"
            idx = data_uri.find(marker)
            if idx <= 5:
                return {"error": f"{provider_name} Gemini image input data URI is malformed", "submit_failed": True}
            mime = data_uri[5:idx].strip().lower() or "image/png"
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": data_uri[idx + len(marker):].strip(),
                }
            })

        if not parts:
            return {"error": f"{provider_name} Gemini image generation requires at least one prompt or image input", "submit_failed": True}

        response_modalities = tool_conf.get("responseModalities") or tool_conf.get("response_modalities") or ["TEXT", "IMAGE"]
        if isinstance(response_modalities, str):
            response_modalities = [response_modalities]
        normalized_modalities = []
        for item in response_modalities if isinstance(response_modalities, list) else []:
            value = str(item or "").strip().upper()
            if value and value not in normalized_modalities:
                normalized_modalities.append(value)
        if "IMAGE" not in normalized_modalities:
            normalized_modalities.append("IMAGE")

        payload: Dict[str, Any] = {
            "contents": [{
                "role": "user",
                "parts": parts,
            }],
            "generationConfig": {
                "responseModalities": normalized_modalities,
            },
        }

        image_config: Dict[str, Any] = {}
        normalized_aspect_ratio = self._normalize_aspect_ratio_value(aspect_ratio or tool_conf.get("aspect_ratio") or tool_conf.get("aspectRatio"))
        if normalized_aspect_ratio and normalized_aspect_ratio != "adaptive":
            image_config["aspectRatio"] = normalized_aspect_ratio

        normalized_image_size = self._normalize_image_size_value(image_size or tool_conf.get("image_size") or tool_conf.get("imageSize"))
        if normalized_image_size:
            model_lower = model.lower()
            if "gemini-3-pro-image-preview" in model_lower or "gemini-3.1-flash-image-preview" in model_lower:
                image_config["imageSize"] = normalized_image_size

        if image_config:
            payload["generationConfig"]["imageConfig"] = image_config

        if config.get("has_google_search") or tool_conf.get("has_google_search"):
            payload["tools"] = [{"google_search": {}}]

        if config.get("has_thinking_mode") or tool_conf.get("has_thinking_mode"):
            think_level = str(config.get("thinking_level") or tool_conf.get("thinking_level") or "high").lower()
            if think_level not in ["minimal", "high"]: think_level = "high"
            payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": think_level, "includeThoughts": True}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        prefer_no_proxy = self._should_prefer_no_proxy(provider_name, "n1n_gemini_image")

        def _post(use_proxy=True, connect_timeout=None):
            c_timeout = connect_timeout or 120
            return self._post_json_request(submit_url, payload, headers, (c_timeout, 120), verify=False, use_proxy=use_proxy)

        def _extract_generated_image(value: Any) -> Optional[str]:
            if isinstance(value, dict):
                for key in ["inline_data", "inlineData"]:
                    inline_block = value.get(key)
                    if isinstance(inline_block, dict):
                        mime = str(inline_block.get("mime_type") or inline_block.get("mimeType") or "").strip().lower()
                        data = str(inline_block.get("data") or "").strip()
                        if mime.startswith("image/") and data:
                            return f"data:{mime};base64,{data}"
                for key in ["url", "imageUrl", "image_url"]:
                    candidate = value.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
                preferred_keys = ["parts", "content", "contents", "candidates", "data", "result", "results", "response"]
                for key in preferred_keys:
                    found = _extract_generated_image(value.get(key))
                    if found:
                        return found
                for nested in value.values():
                    found = _extract_generated_image(nested)
                    if found:
                        return found
            elif isinstance(value, list):
                for item in value:
                    found = _extract_generated_image(item)
                    if found:
                        return found
            elif isinstance(value, str):
                raw = value.strip()
                if raw.startswith("data:image/") or raw.lower().startswith(("http://", "https://")):
                    return raw
            return None

        try:
            try:
                resp = await asyncio.to_thread(_post, not prefer_no_proxy)
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if prefer_no_proxy:
                    raise
                _debug_log(f"[n1n_gemini_image] Connection Failed with Proxy ({str(e)[:50]}...). Retrying without proxy (connect_timeout=15s)...", "warning")
                resp = await asyncio.to_thread(_post, False, 15)

            if resp.status_code != 200:
                _debug_log(f"[n1n_gemini_image] Error {resp.status_code}: {resp.text}", "error")
                return {"error": f"n1n API Error {resp.status_code}", "details": resp.text, "submit_failed": True}

            data = resp.json()
            _debug_log(f"[n1n_gemini_image] API Response: {_strip_base64_from_log(data)}")
            generated_image = _extract_generated_image(data)
            if not generated_image:
                return {
                    "error": "n1n Gemini response did not include an image output",
                    "details": _strip_base64_from_log(data),
                    "submit_failed": True,
                }

            metadata = {
                "raw": data,
                "provider": "n1n",
                "model": model,
                "submit_url": submit_url,
                "endpoint_family": "/v1beta/models/{model}:generateContent",
            }
            return {"url": generated_image, "metadata": metadata}
        except requests.exceptions.Timeout as e:
            _debug_log(f"[n1n_gemini_image] Timeout: {e}", "error")
            return {"error": "n1n upstream request timeout", "details": str(e), "submit_failed": True}
        except requests.exceptions.RequestException as e:
            _debug_log(f"[n1n_gemini_image] RequestException: {e}", "error")
            return {"error": "n1n upstream request failed", "details": str(e), "submit_failed": True}
        except Exception as e:
            _debug_log(f"[n1n_gemini_image] Exception: {e}", "error")
            return {"error": str(e), "submit_failed": True}

    async def _handle_n1n_kling_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None, duration=5, aspect_ratio=None, negative_prompt: Optional[str] = None, image_size: Optional[str] = None):
        provider_name = self._vendor_label(config.get("provider") or ((config.get("config") or {}).get("provider")) or "n1n")
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            return {"error": f"No {provider_name} API Key", "submit_failed": True}

        if gen_type != "image":
            return {"error": f"{provider_name} generation type not supported yet: {gen_type}", "submit_failed": True}

        tool_conf = config.get("config", {}) or {}
        base_url = str(config.get("base_url") or "https://api.n1n.ai").strip().rstrip("/")
        endpoint = str(tool_conf.get("endpoint") or tool_conf.get("endpoint_hint") or "/kling/v1/images/generations").strip()
        submit_url = endpoint if re.match(r"^https?://", endpoint, flags=re.IGNORECASE) else f"{base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"

        configured_model_name = str(
            tool_conf.get("model_name")
            or tool_conf.get("modelName")
            or ((tool_conf.get("n1n") or {}).get("model_name") if isinstance(tool_conf.get("n1n"), dict) else "")
            or ((tool_conf.get("n1n") or {}).get("kling_model_name") if isinstance(tool_conf.get("n1n"), dict) else "")
            or ""
        ).strip()
        has_ref_image = bool(ref_image)
        model_name = configured_model_name or ("kling-v1-5" if has_ref_image else "kling-v1")

        payload: Dict[str, Any] = {
            "model_name": model_name,
            "prompt": str(prompt or "").strip(),
            "n": int(tool_conf.get("n") or 1),
        }

        neg_prompt = str(negative_prompt or tool_conf.get("negative_prompt") or tool_conf.get("negativePrompt") or "").strip()
        if neg_prompt:
            payload["negative_prompt"] = neg_prompt

        normalized_image_size = self._normalize_image_size_value(
            image_size or tool_conf.get("image_size") or tool_conf.get("imageSize") or tool_conf.get("resolution")
        )
        resolution_value = str(tool_conf.get("resolution") or (normalized_image_size.lower() if normalized_image_size else "")).strip().lower()
        if resolution_value in {"1k", "2k"}:
            payload["resolution"] = resolution_value

        normalized_aspect_ratio = self._normalize_aspect_ratio_value(aspect_ratio or tool_conf.get("aspect_ratio") or tool_conf.get("aspectRatio"))
        if normalized_aspect_ratio and normalized_aspect_ratio != "adaptive":
            payload["aspect_ratio"] = normalized_aspect_ratio

            resolved_refs = self._resolve_ref_list_for_api(
                ref_image,
                force_data_uri_for_local=True,
                prefer_public_upload_url=True,
                data_uri_profile="n1n_image_ref",
            ) if ref_image else []
        if resolved_refs:
            payload["image"] = resolved_refs[0]
            payload["image_reference"] = str(tool_conf.get("image_reference") or tool_conf.get("imageReference") or "subject").strip() or "subject"
            image_fidelity = tool_conf.get("image_fidelity") if tool_conf.get("image_fidelity") is not None else tool_conf.get("imageFidelity")
            human_fidelity = tool_conf.get("human_fidelity") if tool_conf.get("human_fidelity") is not None else tool_conf.get("humanFidelity")
            if image_fidelity is None:
                image_fidelity = 0.5
            payload["image_fidelity"] = image_fidelity
            if human_fidelity is not None:
                payload["human_fidelity"] = human_fidelity

        internal_callback_url = str(tool_conf.get("_provider_callback_url") or "").strip()
        raw_callback_url = str(internal_callback_url or tool_conf.get("callback_url") or tool_conf.get("callbackUrl") or tool_conf.get("callBackUrl") or "").strip()
        callback_ticket = str(tool_conf.get("_provider_callback_ticket") or "").strip() or "n1n-kling-image"
        callback_tool_conf = dict(tool_conf or {})
        if raw_callback_url:
            callback_tool_conf.setdefault("callback_url", raw_callback_url)
        callback_url = self._resolve_provider_callback_url(callback_tool_conf, callback_ticket)
        if callback_url and callback_url != raw_callback_url:
            logger.info(
                "n1n Kling callback auto-assigned | ticket=%s callback_url=%s raw_callback=%s",
                callback_ticket,
                callback_url,
                raw_callback_url or None,
            )
        if callback_url:
            payload["callback_url"] = callback_url

        extra_metadata = {
            "provider": provider_name,
            "model": model_name,
            "prompt": prompt,
            "submit_url": submit_url,
            "endpoint_family": "/kling/v1/images/generations",
        }
        return await self._submit_and_poll_image_task(submit_url, payload, api_key, f"{str(provider_name).lower()}_kling_image", extra_metadata=extra_metadata)

    async def _handle_stability_generation(self, gen_type, prompt, config, ref_image=None, negative_prompt: Optional[str] = None):
        if gen_type != "image": return {"error": "Stability only supports image"}
        
        api_key = config.get("api_key")
        tool_conf = config.get("config", {}) or {}
        endpoint = tool_conf.get("endpoint") or "https://api.stability.ai"
        endpoint = endpoint.rstrip("/")
        model = config.get("model") or "stable-diffusion-xl-1024-v1-0"
        
        base_metadata = {"provider": "stability", "model": model, "prompt": prompt}
        
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
        
        # I2I
        if ref_image:
             url = f"{endpoint}/v1/generation/{model}/image-to-image"
             ref_bytes = None

             if self._is_public_http_url(ref_image):
                 try:
                     resp = await asyncio.to_thread(lambda: requests.get(ref_image, timeout=30))
                     if resp.status_code == 200:
                         ref_bytes = resp.content
                 except Exception:
                     ref_bytes = None
             else:
                 b64 = await self._get_image_base64_for_api_async(ref_image)
                 if b64 and b64 != ref_image:
                     ref_bytes = base64.b64decode(b64)
            
             if ref_bytes:
                 files = {"init_image": ("init_image.png", ref_bytes, "image/png")}
                 data = {"text_prompts[0][text]": prompt, "init_image_mode": "IMAGE_STRENGTH", "image_strength": 0.35}
                 if str(negative_prompt or "").strip():
                     data["text_prompts[1][text]"] = str(negative_prompt).strip()
                     data["text_prompts[1][weight]"] = -1
                 
                 def _post_i2i(): return requests.post(url, headers=headers, files=files, data=data, timeout=(15, 120), verify=False)
                 resp = await asyncio.to_thread(_post_i2i)
             else:
                 return {"error": "Could not load reference image"}

        else:
             # T2I
             url = f"{endpoint}/v1/generation/{model}/text-to-image"
             headers["Content-Type"] = "application/json"
             cfg_scale = 7.0
             try:
                 configured_cfg = tool_conf.get("cfg_scale")
                 if configured_cfg is None:
                     configured_cfg = tool_conf.get("cfg")
                 if configured_cfg is not None:
                     parsed_cfg = float(configured_cfg)
                     if parsed_cfg > 0:
                         cfg_scale = parsed_cfg
             except Exception:
                 pass
             body = {"text_prompts": [{"text": prompt}], "cfg_scale": cfg_scale, "height": 1024, "width": 1024, "samples": 1}
             if str(negative_prompt or "").strip():
                 body["text_prompts"].append({"text": str(negative_prompt).strip(), "weight": -1})
             def _post_t2i(): return requests.post(url, headers=headers, json=body, timeout=(15, 120), verify=False)
             resp = await asyncio.to_thread(_post_t2i)
        
        if resp.status_code != 200: return {"error": f"Stability Error {resp.status_code}", "details": resp.text}
        
        data = resp.json()
        artifacts = data.get("artifacts", [])
        if artifacts:
             b64 = artifacts[0].get("base64")
             try:
                 meta = {"raw": data}
                 meta.update(base_metadata)
                 return {"url": f"data:image/png;base64,{b64}", "metadata": meta}
             except Exception as e:
                 return {"error": f"Failed to save image: {e}"}
        return {"error": "No artifacts"}

    # --- Helper to Common Requests ---