
@router.post("/analyze_scene", response_model=Dict[str, Any])
async def analyze_scene(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), async_mode: str = Query("0")): # user auth optional depending on reqs, kept for safety
    """
    Submits raw script text to LLM for Scene/Beat analysis using a specific prompt template.
    Returns the raw analysis result (Markdown/JSON).
    """
    if async_mode == "1":
        dedup_key = _build_analyze_scene_dedup_key(current_user.id, request)
        now_ts = time.time()
        reused_task_id = ""
        reused_status = ""

        with _ANALYZE_SCENE_RECENT_TASKS_LOCK:
            _prune_recent_analyze_scene_tasks_locked(now_ts)
            existing = _ANALYZE_SCENE_RECENT_TASKS.get(dedup_key) or {}
            existing_task_id = str(existing.get("task_id") or "").strip()
            if existing_task_id:
                info = _get_task_status(existing_task_id, user_id=current_user.id) or {}
                status = str(info.get("status") or "").strip().lower()
                if status in {"pending", "running", "completed"}:
                    reused_task_id = existing_task_id
                    reused_status = status
                else:
                    _ANALYZE_SCENE_RECENT_TASKS.pop(dedup_key, None)

        if reused_task_id:
            logger.warning(
                "[analyze_scene] deduplicated async submit user_id=%s episode_id=%s task_id=%s status=%s window_s=%s",
                current_user.id,
                getattr(request, "episode_id", None),
                reused_task_id,
                reused_status,
                _ANALYZE_SCENE_DEDUP_WINDOW_SECONDS,
            )
            return JSONResponse({
                "task_id": reused_task_id,
                "async": True,
                "deduplicated": True,
                "status": reused_status,
            })

        tid = _submit_async(analyze_scene, user_id=current_user.id, kind="analyze_scene",
                            request=request, async_mode="0")
        with _ANALYZE_SCENE_RECENT_TASKS_LOCK:
            _prune_recent_analyze_scene_tasks_locked(now_ts)
            _ANALYZE_SCENE_RECENT_TASKS[dedup_key] = {
                "task_id": tid,
                "ts": now_ts,
                "episode_id": getattr(request, "episode_id", None),
            }
        return JSONResponse({"task_id": tid, "async": True})
    logger.info("Received analyze_scene request")
    try:
        logger.info(f"[analyze_scene] request.episode_id={getattr(request, 'episode_id', None)}")
    except Exception:
        pass
    if request.project_metadata:
        try:
            keys = list(request.project_metadata.keys())
        except Exception:
            keys = []
        logger.info(f"Project Metadata received (keys only): {keys}")
    else:
        logger.info("No Project Metadata received")

    try:
        # Cache user primitives before releasing DB session for long LLM calls.
        current_user_id = int(getattr(current_user, "id", 0) or 0)
        current_user_is_superuser = bool(getattr(current_user, "is_superuser", False))

        def _is_length_finish_reason(reason: Any) -> bool:
            r = str(reason or "").strip().lower().replace("-", "_")
            return r in {
                "length",
                "max_tokens",
                "max_token",
                "max_output_tokens",
                "output_token_limit",
                "token_limit",
            }

        def _estimate_tokens(text: str) -> int:
            if not text:
                return 0
            # Heuristic: ~4 bytes per token (good enough for debug)
            return (len(text.encode("utf-8")) + 3) // 4

        def _merge_usage(total: Dict[str, Any], part: Dict[str, Any]) -> Dict[str, Any]:
            total = dict(total or {})
            part = dict(part or {})

            def _add(key: str, value: Any):
                if value is None:
                    return
                try:
                    iv = int(value)
                except Exception:
                    return
                total[key] = int(total.get(key) or 0) + iv

            # Common OpenAI-style keys
            _add("prompt_tokens", part.get("prompt_tokens"))
            _add("completion_tokens", part.get("completion_tokens"))
            _add("total_tokens", part.get("total_tokens"))
            # Some providers use input/output naming
            _add("input_tokens", part.get("input_tokens"))
            _add("output_tokens", part.get("output_tokens"))

            # Preserve provider-specific extra usage fields if they are scalar and not already present
            for k, v in part.items():
                if k in total:
                    continue
                if isinstance(v, (int, float, str)):
                    total[k] = v
            return total

        def _detect_scene_output_sections(output_text: str) -> Dict[str, Any]:
            text = str(output_text or "")
            checks = {
                "part_1": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Part\s*1\b"),
                "subject_index": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Subject\s*Index\b"),
                "part_2": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Part\s*2\b"),
                "final_consistency_report": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Final\s+Consistency\s+Report\b"),
            }
            found_sections: Dict[str, bool] = {k: bool(p.search(text)) for k, p in checks.items()}
            missing_sections = [k for k, present in found_sections.items() if not present]
            return {
                "found_sections": found_sections,
                "missing_sections": missing_sections,
                "structure_incomplete": bool(missing_sections),
            }

        def _detect_output_integrity(output_text: str, segments: List[Dict[str, Any]], final_finish_reason: Optional[str]) -> Dict[str, Any]:
            text = (output_text or "").strip()
            segment_list = segments or []
            had_length_finish = any(_is_length_finish_reason(seg.get("finish_reason")) for seg in segment_list)
            ended_with_length = _is_length_finish_reason(final_finish_reason)
            section_meta = _detect_scene_output_sections(text)
            missing_sections = section_meta.get("missing_sections") or []
            structure_incomplete = bool(section_meta.get("structure_incomplete"))

            json_candidate = ""
            json_expected = False
            explicit_json_response = False
            parseable_json_block_count = 0

            if text.startswith("```"):
                lowered = text.lower()
                if "```json" in lowered or ("```" in lowered and ("{" in text or "[" in text)):
                    json_expected = True
                    fence_start = text.find("\n")
                    fence_end = text.rfind("```")
                    if fence_start != -1 and fence_end != -1 and fence_end > fence_start:
                        json_candidate = text[fence_start + 1:fence_end].strip()

            if not json_candidate:
                if text.startswith("{") or text.startswith("["):
                    json_expected = True
                    explicit_json_response = True
                    json_candidate = text
                else:
                    first_obj = text.find("{")
                    last_obj = text.rfind("}")
                    first_arr = text.find("[")
                    last_arr = text.rfind("]")
                    if first_obj != -1 and last_obj > first_obj:
                        json_expected = True
                        json_candidate = text[first_obj:last_obj + 1].strip()
                    elif first_arr != -1 and last_arr > first_arr:
                        json_expected = True
                        json_candidate = text[first_arr:last_arr + 1].strip()

            # Non-blocking fallback: count parseable fenced JSON blocks in mixed markdown outputs.
            try:
                fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
                for m in fence_re.finditer(text):
                    candidate = str(m.group(1) or "").strip()
                    if not candidate:
                        continue
                    try:
                        json.loads(candidate)
                        parseable_json_block_count += 1
                    except Exception:
                        continue
            except Exception:
                parseable_json_block_count = 0

            json_valid = None
            json_error = None
            if json_expected:
                try:
                    json.loads(json_candidate)
                    json_valid = True
                except Exception as parse_error:
                    json_valid = False
                    json_error = str(parse_error)

            truncation_suspected = bool(
                ended_with_length
                or (had_length_finish and json_expected and json_valid is False)
                or structure_incomplete
            )

            warning_codes: List[str] = []
            warnings: List[str] = []
            if ended_with_length:
                warning_codes.append("ANALYSIS_OUTPUT_TRUNCATED")
                warnings.append("Analysis output may be incomplete because the response hit a length limit.")
            elif had_length_finish:
                warning_codes.append("ANALYSIS_OUTPUT_CONTINUED")
                warnings.append("Analysis response was split by length limits and auto-continuation was applied.")

            # Only flag JSON invalid for explicit pure-JSON responses.
            # Mixed markdown + partial JSON should stay non-blocking.
            should_flag_json_invalid = bool(json_expected and json_valid is False and explicit_json_response)
            if should_flag_json_invalid:
                warning_codes.append("ANALYSIS_JSON_INVALID")
                warnings.append("Analysis returned invalid or incomplete JSON. Please review before applying.")

            if structure_incomplete:
                warning_codes.append("ANALYSIS_STRUCTURE_INCOMPLETE")
                warnings.append(
                    "Analysis output is missing required sections: "
                    + ", ".join([str(x) for x in missing_sections])
                    + "."
                )

            return {
                "truncation_detected": had_length_finish,
                "truncation_suspected": truncation_suspected,
                "ended_with_length": ended_with_length,
                "json_expected": json_expected,
                "json_valid": json_valid,
                "json_error": json_error,
                "explicit_json_response": explicit_json_response,
                "parseable_json_block_count": parseable_json_block_count,
                "found_sections": section_meta.get("found_sections") or {},
                "missing_sections": missing_sections,
                "structure_incomplete": structure_incomplete,
                "warning_codes": warning_codes,
                "warnings": warnings,
            }

        def _normalize_subject_name(value: Any) -> str:
            text = str(value or "").strip()
            if not text:
                return ""
            text = re.sub(r"^(?:CHAR|PROP|ENV)\s*:\s*", "", text, flags=re.IGNORECASE)
            text = text.strip()
            if text.startswith("[") and text.endswith("]"):
                text = text[1:-1].strip()
            text = text.lstrip("@").strip()
            text = re.sub(
                r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+",
                lambda match: re.sub(r"[_-]+", " ", match.group(0)),
                text,
            )
            text = re.sub(r"\s+", " ", text)
            return text

        def _normalize_subject_compare_key(value: Any) -> str:
            stable = _normalize_subject_name(value)
            if not stable:
                return ""
            # Insert spaces for camelCase/PascalCase boundaries before compact compare.
            stable = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stable)
            stable = normalize_entity_token(stable)
            # Treat spaces/underscores/hyphens as equivalent for EN names.
            stable = re.sub(r"[\s_\-]+", "", stable)
            # Remove remaining punctuation/noise while keeping CJK/letters/digits.
            stable = re.sub(r"[^\w\u4e00-\u9fff]", "", stable)
            return stable

        def _extract_subjects_from_analysis_text(text: str) -> List[str]:
            raw = str(text or "")
            if not raw:
                return []
            patterns = [
                re.compile(r"CHAR\s*:\s*\[@([^\]]+)\]", re.IGNORECASE),
                re.compile(r"PROP\s*:\s*\[([^\]]+)\]", re.IGNORECASE),
                re.compile(r"ENV\s*:\s*\[([^\]]+)\]", re.IGNORECASE),
            ]
            found: List[str] = []
            seen = set()
            for pattern in patterns:
                for m in pattern.finditer(raw):
                    normalized = _normalize_subject_name(m.group(1))
                    key = _normalize_subject_compare_key(normalized)
                    if normalized and key not in seen:
                        seen.add(key)
                        found.append(normalized)
            return found

        def _extract_entities_from_json_candidates(text: str) -> Dict[str, List[Dict[str, Any]]]:
            payload: Dict[str, List[Dict[str, Any]]] = {
                "characters": [], "covers": [],
                "props": [],
                "environments": [],
            }
            raw = str(text or "")
            if not raw:
                return payload

            candidates: List[str] = []
            fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
            for m in fence_re.finditer(raw):
                candidate = str(m.group(1) or "").strip()
                if candidate:
                    candidates.append(candidate)

            trimmed = raw.strip()
            if trimmed.startswith("{") and trimmed.endswith("}"):
                candidates.append(trimmed)

            seen_candidate = set()
            for candidate in candidates:
                key = candidate[:2000]
                if key in seen_candidate:
                    continue
                seen_candidate.add(key)
                try:
                    obj = json.loads(candidate)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                for section in ("characters", "props", "environments", "covers"):
                    items = obj.get(section)
                    if isinstance(items, list):
                        payload[section].extend([x for x in items if isinstance(x, dict)])
