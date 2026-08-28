# -*- coding: utf-8 -*-
"""AgentScope post-optimizer for storyboard Video Content (CN).

Main shot drafting still uses ``skills/shot_generation.md`` via
``llm_service.generate_content_with_fallback``. After a valid draft table
exists, an optional AgentScope ReAct agent polishes **only**
``Video Content (CN)`` using ``skills/shot_video_prompt_optimize_agentscope.md``.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

EventCallback = Optional[Callable[[Dict[str, Any]], Any]]

from app.services.llm_service import llm_service
from app.services.prompt_resolve import _resolve_prompt_text
from app.services.shot_markdown import (
    parse_shots_markdown_table,
    sanitize_shots_markdown_table_text,
)

logger = logging.getLogger("api_logger")

_OPTIMIZE_PROMPT_FILE = "skills/shot_video_prompt_optimize_agentscope.md"
_AGENTSCOPE_SKILL_ROOT = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "prompts"
    / "agentscope_skills"
    / "shot_video_prompt_optimize"
)

_NON_VIDEO_COMPARE_KEYS = [
    "Shot ID",
    "Shot Name",
    "Scene ID",
    "Shot Logic (CN)",
    "Start Frame",
    "Video Content",
    "Duration (s)",
    "Keyframes",
    "End Frame",
    "Start Frame (CN)",
    "Keyframes (CN)",
    "End Frame (CN)",
    "Associated Entities",
]


def _env_optimize_enabled() -> bool:
    raw = str(os.getenv("SHOT_VIDEO_PROMPT_OPTIMIZE_AGENT", "on") or "").strip().lower()
    if raw in {"0", "false", "off", "no", "legacy", "disable", "disabled"}:
        return False
    return True


def _agentscope_importable() -> bool:
    """agentscope>=2 needs Python >=3.11; Render 3.10 builds omit it."""
    try:
        import agentscope  # noqa: F401
        return True
    except ImportError:
        return False


def _should_skip_agentscope_for_config(llm_config: Dict[str, Any]) -> bool:
    provider = str((llm_config or {}).get("provider") or "").strip().lower()
    model = str((llm_config or {}).get("model") or "").strip().lower()
    base_url = str((llm_config or {}).get("base_url") or "").strip().lower()
    if provider in {"kie", "aiclub"}:
        return True
    if "claude" in model or "anthropic" in provider or "anthropic" in base_url:
        return True
    return False


def _extract_nested_config(llm_config: Dict[str, Any]) -> Dict[str, Any]:
    nested = llm_config.get("config") if isinstance(llm_config.get("config"), dict) else {}
    return nested if isinstance(nested, dict) else {}


def _resolve_openai_compatible_endpoint(llm_config: Dict[str, Any]) -> Tuple[str, str, str, Dict[str, Any]]:
    nested = _extract_nested_config(llm_config)
    api_key = str(llm_config.get("api_key") or nested.get("api_key") or "").strip()
    base_url = str(llm_config.get("base_url") or nested.get("base_url") or "").strip()
    model = str(llm_config.get("model") or nested.get("model") or "").strip()
    generate_kwargs: Dict[str, Any] = {}
    for src in (nested, llm_config):
        for key in ("temperature", "top_p", "max_tokens"):
            if key in src and src.get(key) is not None and key not in generate_kwargs:
                generate_kwargs[key] = src.get(key)
    return api_key, model, base_url, generate_kwargs


def _merge_usage(a: Any, b: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for src in (a, b):
        if not isinstance(src, dict):
            continue
        for key in ("input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "total_tokens"):
            if src.get(key) is None:
                continue
            try:
                out[key] = int(out.get(key) or 0) + int(src.get(key) or 0)
            except Exception:
                continue
    if "input_tokens" in out and "prompt_tokens" not in out:
        out["prompt_tokens"] = out["input_tokens"]
    if "output_tokens" in out and "completion_tokens" not in out:
        out["completion_tokens"] = out["output_tokens"]
    if "total_tokens" not in out and ("input_tokens" in out or "output_tokens" in out):
        out["total_tokens"] = int(out.get("input_tokens") or 0) + int(out.get("output_tokens") or 0)
    return out


def _norm_cell(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").strip()


def _video_only_diff_report(draft_markdown: str, candidate_markdown: str) -> Dict[str, Any]:
    draft_clean = sanitize_shots_markdown_table_text(draft_markdown)
    cand_clean = sanitize_shots_markdown_table_text(candidate_markdown)
    _dh, draft_rows, _ = parse_shots_markdown_table(draft_clean)
    _ch, cand_rows, _ = parse_shots_markdown_table(cand_clean)
    if not draft_rows or not cand_rows:
        return {"ok": False, "error": "unparseable_table", "hint": "Both draft and candidate must be valid shot tables."}
    if len(draft_rows) != len(cand_rows):
        return {
            "ok": False,
            "error": "row_count_mismatch",
            "draft_rows": len(draft_rows),
            "candidate_rows": len(cand_rows),
            "hint": "Do not add/remove/reorder shots; polish Video Content (CN) only.",
        }
    issues: List[str] = []
    video_changed = 0
    for idx, (drow, crow) in enumerate(zip(draft_rows, cand_rows), start=1):
        for key in _NON_VIDEO_COMPARE_KEYS:
            if _norm_cell(drow.get(key)) != _norm_cell(crow.get(key)):
                issues.append(f"row{idx}: non-video column changed: {key}")
        if _norm_cell(drow.get("Video Content (CN)")) != _norm_cell(crow.get("Video Content (CN)")):
            video_changed += 1
        if not _norm_cell(crow.get("Video Content (CN)")):
            issues.append(f"row{idx}: empty Video Content (CN)")
    return {
        "ok": not issues,
        "issues": issues[:20],
        "video_cells_changed": video_changed,
        "hint": "Keep all non-Video columns identical to the draft." if issues else "Video-only polish accepted.",
    }


def _build_optimize_user_prompt(*, draft_markdown: str, scene_context: str = "") -> str:
    ctx = str(scene_context or "").strip()
    ctx_block = f"# Scene Context\n{ctx}\n\n" if ctx else ""
    return (
        f"{ctx_block}"
        "# Draft Shot Table\n"
        "The following table is already generated by the main shot_generation pipeline. "
        "Treat it as the authoritative draft. Polish **only** `Video Content (CN)`.\n\n"
        f"{str(draft_markdown or '').strip()}\n\n"
        "# Instruction\n"
        "1. Improve each `Video Content (CN)` for AI video models "
        "(start with 运镜与动作流, not `ENV:[…]` or 全局动态风格; "
        "P1 staging then 背景参考图为 ENV:; same-ENV later Pn skip restaging; "
        "ENV-name change must restage; 全局动态风格 after all Pn; "
        "do not shorten staging facing/anchors; cover every merged-beat derived ENV).\n"
        "2. Keep Shot ID / Scene ID / Duration / Shot Logic / Associated Entities / empty columns unchanged.\n"
        "3. Keep the same number of rows and order.\n"
        "4. Call `validate_shot_markdown_table` then `diff_video_only_guard` before finalizing.\n"
        "5. Final reply = one markdown table only.\n"
    )


def _build_optimize_tools(draft_markdown: str):
    from agentscope.message import TextBlock, ToolResultState
    from agentscope.permission import PermissionBehavior, PermissionDecision
    from agentscope.tool import FunctionTool, ToolChunk

    class AlwaysAllowFunctionTool(FunctionTool):
        async def check_permissions(self, *_args: Any, **_kwargs: Any) -> PermissionDecision:
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="Shot video optimize tools are always allowed.",
            )

    async def validate_shot_markdown_table(markdown_table: str) -> ToolChunk:
        """Validate Shot List markdown parseability and required columns."""
        cleaned = sanitize_shots_markdown_table_text(markdown_table)
        if not cleaned:
            payload = {"ok": False, "error": "empty_or_unparseable_table"}
            return ToolChunk(
                content=[TextBlock(text=json.dumps(payload, ensure_ascii=False))],
                state=ToolResultState.SUCCESS,
            )
        headers, rows, table_line_count = parse_shots_markdown_table(cleaned)
        required_cols = [
            "Shot ID",
            "Scene ID",
            "Shot Logic (CN)",
            "Duration (s)",
            "Video Content (CN)",
            "Associated Entities",
        ]
        missing_cols = [c for c in required_cols if c not in (headers or [])]
        payload = {
            "ok": bool(rows) and not missing_cols,
            "parsed_rows": len(rows or []),
            "table_line_count": table_line_count,
            "missing_required_columns": missing_cols,
        }
        return ToolChunk(
            content=[TextBlock(text=json.dumps(payload, ensure_ascii=False))],
            state=ToolResultState.SUCCESS,
        )

    async def diff_video_only_guard(markdown_table: str) -> ToolChunk:
        """Ensure candidate table only changed Video Content (CN) vs the draft."""
        payload = _video_only_diff_report(draft_markdown, markdown_table)
        return ToolChunk(
            content=[TextBlock(text=json.dumps(payload, ensure_ascii=False))],
            state=ToolResultState.SUCCESS,
        )

    return [
        AlwaysAllowFunctionTool(
            validate_shot_markdown_table,
            name="validate_shot_markdown_table",
            description="Validate the polished Shot List markdown table structure.",
            is_read_only=True,
        ),
        AlwaysAllowFunctionTool(
            diff_video_only_guard,
            name="diff_video_only_guard",
            description=(
                "Compare candidate table to the original draft and confirm only "
                "Video Content (CN) changed."
            ),
            is_read_only=True,
        ),
    ]


def _usage_from_msg(msg: Any) -> Dict[str, Any]:
    usage: Dict[str, Any] = {}
    raw = getattr(msg, "usage", None)
    if raw is None:
        return usage
    try:
        if hasattr(raw, "model_dump"):
            data = raw.model_dump()
        elif isinstance(raw, dict):
            data = raw
        else:
            data = {
                "input_tokens": getattr(raw, "input_tokens", None),
                "output_tokens": getattr(raw, "output_tokens", None),
            }
        if isinstance(data, dict):
            if data.get("input_tokens") is not None:
                usage["input_tokens"] = int(data.get("input_tokens") or 0)
                usage["prompt_tokens"] = usage["input_tokens"]
            if data.get("output_tokens") is not None:
                usage["output_tokens"] = int(data.get("output_tokens") or 0)
                usage["completion_tokens"] = usage["output_tokens"]
            if "input_tokens" in usage or "output_tokens" in usage:
                usage["total_tokens"] = int(usage.get("input_tokens") or 0) + int(
                    usage.get("output_tokens") or 0
                )
    except Exception:
        return {}
    return usage


async def _emit(on_event: EventCallback, event: Dict[str, Any]) -> None:
    if not on_event:
        return
    try:
        result = on_event(event)
        if hasattr(result, "__await__"):
            await result  # type: ignore[misc]
    except Exception:
        logger.debug("shot_generation_agentscope on_event failed", exc_info=True)


def _map_agentscope_event(evt: Any) -> Optional[Dict[str, Any]]:
    """Map AgentScope stream events to UI-facing SSE payloads."""
    from agentscope.event import EventType

    et = getattr(evt, "type", None)
    if et == EventType.REPLY_START:
        return {"type": "phase", "phase": "agent_reply", "message": "Agent 开始优化视频提示词…"}
    if et == EventType.TEXT_BLOCK_DELTA:
        delta = str(getattr(evt, "delta", "") or "")
        if not delta:
            return None
        return {"type": "token", "content": delta}
    if et == EventType.THINKING_BLOCK_DELTA:
        delta = str(getattr(evt, "delta", "") or "")
        if not delta:
            return None
        return {"type": "token", "content": delta, "channel": "thinking"}
    if et == EventType.TOOL_CALL_START:
        return {
            "type": "tool_start",
            "tool": str(getattr(evt, "tool_call_name", "") or "tool"),
            "parameters": {},
        }
    if et == EventType.TOOL_RESULT_TEXT_DELTA:
        delta = str(getattr(evt, "delta", "") or "")
        if not delta:
            return None
        return {
            "type": "tool_result",
            "tool": "tool",
            "status": "running",
            "result": delta,
        }
    if et == EventType.TOOL_RESULT_END:
        return {
            "type": "tool_result",
            "tool": str(getattr(evt, "tool_call_id", "") or "tool"),
            "status": str(getattr(evt, "state", "") or "success"),
            "result": "",
        }
    if et == EventType.REPLY_END:
        return {"type": "phase", "phase": "agent_reply_end", "message": "Agent 优化回合结束"}
    if et == EventType.EXCEED_MAX_ITERS:
        return {"type": "phase", "phase": "agent_max_iters", "message": "Agent 达到最大迭代次数"}
    return None


async def _iter_video_optimize_agent(
    *,
    draft_markdown: str,
    scene_context: str,
    llm_config: Dict[str, Any],
    on_event: EventCallback = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Yield SSE-shaped events, then a final ``{"type":"_result", ...}``."""
    from agentscope.agent import Agent, ReActConfig
    from agentscope.credential import OpenAICredential
    from agentscope.event import EventType
    from agentscope.message import Msg, UserMsg
    from agentscope.model import OpenAIChatModel
    from agentscope.permission import PermissionMode
    from agentscope.state import AgentState
    from agentscope.tool import Toolkit

    api_key, model, base_url, generate_kwargs = _resolve_openai_compatible_endpoint(llm_config)
    if not api_key:
        raise RuntimeError("agentscope_missing_api_key")
    if not model:
        raise RuntimeError("agentscope_missing_model")

    system_prompt = _resolve_prompt_text(_OPTIMIZE_PROMPT_FILE)
    user_input = _build_optimize_user_prompt(
        draft_markdown=draft_markdown,
        scene_context=scene_context,
    )

    credential = OpenAICredential(api_key=api_key, base_url=base_url or None)
    parameters = OpenAIChatModel.Parameters(
        temperature=generate_kwargs.get("temperature"),
        top_p=generate_kwargs.get("top_p"),
        max_tokens=generate_kwargs.get("max_tokens"),
        parallel_tool_calls=False,
    )
    chat_model = OpenAIChatModel(
        credential=credential,
        model=model,
        parameters=parameters,
        stream=True,
    )
    toolkit = Toolkit(
        tools=_build_optimize_tools(draft_markdown),
        skills_or_loaders=[str(_AGENTSCOPE_SKILL_ROOT)] if _AGENTSCOPE_SKILL_ROOT.is_dir() else None,
    )
    state = AgentState()
    state.permission_context.mode = PermissionMode.BYPASS
    agent = Agent(
        name="ShotVideoPromptOptimizeAgent",
        system_prompt=system_prompt,
        model=chat_model,
        toolkit=toolkit,
        state=state,
        react_config=ReActConfig(max_iters=6),
    )

    await _emit(on_event, {
        "type": "phase",
        "phase": "optimizing",
        "message": "AgentScope 正在流式优化 Video Content (CN)…",
    })

    final_msg: Optional[Msg] = None
    async for evt in agent.reply_stream(
        UserMsg("user", user_input),
        yield_final_msg=True,
    ):
        if isinstance(evt, Msg):
            final_msg = evt
            continue
        mapped = _map_agentscope_event(evt)
        if mapped:
            await _emit(on_event, mapped)
            yield mapped
        # Also surface reply_end reason briefly
        if getattr(evt, "type", None) == EventType.REPLY_END and final_msg is None:
            # final msg may arrive as separate yield when yield_final_msg=True
            pass

    content = (final_msg.get_text_content() or "").strip() if final_msg is not None else ""
    result = {
        "type": "_result",
        "content": content,
        "usage": _usage_from_msg(final_msg),
        "_agentscope_optimize": True,
        "_provider": llm_config.get("provider"),
        "_model": model,
    }
    yield result


async def generate_shots_content(
    user_input: str,
    system_prompt: str,
    llm_config: Dict[str, Any],
    *,
    response_validator: Optional[Callable[..., Any]] = None,
    context: str = "ai_generate_shots",
    on_event: EventCallback = None,
) -> Dict[str, Any]:
    """Draft with shot_generation.md, then optionally AgentScope-polish Video CN."""
    await _emit(on_event, {
        "type": "phase",
        "phase": "drafting",
        "message": "主分镜生成中（shot_generation.md）…",
    })
    draft = await llm_service.generate_content_with_fallback(
        user_input,
        system_prompt,
        llm_config,
        response_validator=response_validator,
    )
    draft_content = str((draft or {}).get("content") or "").strip()
    if not draft_content or draft_content.startswith("Error:"):
        return draft

    await _emit(on_event, {
        "type": "phase",
        "phase": "draft_ready",
        "message": f"草稿表已生成（{len(draft_content)} 字符），准备 Agent 优化…",
    })

    if (
        not _env_optimize_enabled()
        or _should_skip_agentscope_for_config(llm_config or {})
        or not _agentscope_importable()
    ):
        logger.info("[%s] video_optimize_skipped", context)
        await _emit(on_event, {"type": "phase", "phase": "optimize_skipped", "message": "已跳过视频提示词优化"})
        return draft

    draft_table = sanitize_shots_markdown_table_text(draft_content)
    if not draft_table:
        return draft

    try:
        logger.info(
            "[%s] video_optimize_start provider=%s model=%s prompt=%s",
            context,
            (llm_config or {}).get("provider"),
            (llm_config or {}).get("model"),
            _OPTIMIZE_PROMPT_FILE,
        )
        optimized: Optional[Dict[str, Any]] = None
        async for item in _iter_video_optimize_agent(
            draft_markdown=draft_table,
            scene_context=str(user_input or ""),
            llm_config=llm_config or {},
            on_event=on_event,
        ):
            if isinstance(item, dict) and item.get("type") == "_result":
                optimized = item
        if not optimized:
            logger.warning("[%s] video_optimize_empty; keep draft", context)
            await _emit(on_event, {"type": "phase", "phase": "optimize_fallback", "message": "优化无输出，保留草稿"})
            return draft

        opt_content = str((optimized or {}).get("content") or "").strip()
        if not opt_content:
            logger.warning("[%s] video_optimize_empty; keep draft", context)
            await _emit(on_event, {"type": "phase", "phase": "optimize_fallback", "message": "优化无输出，保留草稿"})
            return draft

        guard = _video_only_diff_report(draft_table, opt_content)
        if not guard.get("ok"):
            logger.warning(
                "[%s] video_optimize_guard_failed issues=%s; keep draft",
                context,
                (guard.get("issues") or guard.get("error") or "")[:400],
            )
            await _emit(on_event, {
                "type": "phase",
                "phase": "optimize_fallback",
                "message": "优化护栏未通过，保留草稿",
            })
            return draft

        if response_validator is not None:
            probe = {
                "content": opt_content,
                "usage": _merge_usage((draft or {}).get("usage"), (optimized or {}).get("usage")),
            }
            ok, reason, _meta = response_validator(probe, llm_config or {})
            if not ok:
                logger.warning(
                    "[%s] video_optimize_validator_failed reason=%s; keep draft",
                    context,
                    str(reason or "")[:400],
                )
                await _emit(on_event, {
                    "type": "phase",
                    "phase": "optimize_fallback",
                    "message": "优化结果校验失败，保留草稿",
                })
                return draft

        merged = dict(draft or {})
        merged["content"] = opt_content
        merged["usage"] = _merge_usage((draft or {}).get("usage"), (optimized or {}).get("usage"))
        merged["_agentscope_optimize"] = True
        merged["_video_cells_changed"] = guard.get("video_cells_changed")
        logger.info(
            "[%s] video_optimize_ok changed_cells=%s",
            context,
            guard.get("video_cells_changed"),
        )
        await _emit(on_event, {
            "type": "phase",
            "phase": "optimize_done",
            "message": f"视频提示词优化完成（改动 {guard.get('video_cells_changed') or 0} 格）",
        })
        return merged
    except Exception as exc:
        logger.warning(
            "[%s] video_optimize_failed error=%s; keep draft",
            context,
            exc,
            exc_info=True,
        )
        await _emit(on_event, {
            "type": "phase",
            "phase": "optimize_fallback",
            "message": f"优化失败，保留草稿：{exc}",
        })
        return draft


async def iter_generate_shots_content_events(
    user_input: str,
    system_prompt: str,
    llm_config: Dict[str, Any],
    *,
    response_validator: Optional[Callable[..., Any]] = None,
    context: str = "ai_generate_shots",
) -> AsyncIterator[Dict[str, Any]]:
    """Async generator of SSE events + final ``done`` with ``result`` dict for content only."""
    queue: List[Dict[str, Any]] = []

    def _capture(event: Dict[str, Any]) -> None:
        queue.append(event)

    # Drain helper while work runs: run generate and yield captured events incrementally via a queue.
    import asyncio

    result_box: Dict[str, Any] = {}
    error_box: Dict[str, Any] = {}

    async def _worker() -> None:
        try:
            result_box["value"] = await generate_shots_content(
                user_input,
                system_prompt,
                llm_config,
                response_validator=response_validator,
                context=context,
                on_event=_capture,
            )
        except Exception as exc:
            error_box["error"] = exc

    task = asyncio.create_task(_worker())
    while not task.done() or queue:
        while queue:
            yield queue.pop(0)
        if not task.done():
            await asyncio.sleep(0.05)
    await task
    if error_box.get("error"):
        yield {"type": "error", "message": str(error_box["error"])}
        return
    yield {"type": "content_ready", "result": result_box.get("value") or {}}
