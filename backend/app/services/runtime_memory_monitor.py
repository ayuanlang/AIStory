# -*- coding: utf-8 -*-
"""Process / GC / in-memory store diagnostics for admin console."""
from __future__ import annotations

import gc
import json
import os
import sys
import threading
import time
import tracemalloc
from itertools import islice
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.time_utils import now_bj_iso

_PROCESS_STARTED_UNIX_TS = time.time()
_STORE_SAMPLE_ITEMS = max(4, min(64, int(os.getenv("RUNTIME_MEMORY_STORE_SAMPLE_ITEMS", "24") or 24)))
_TRACEMALLOC_TOP = max(5, min(50, int(os.getenv("RUNTIME_MEMORY_TRACEMALLOC_TOP", "15") or 15)))


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _bytes_to_mb(value: Any) -> Optional[float]:
    raw = _safe_int(value)
    if raw is None:
        return None
    return round(raw / (1024.0 * 1024.0), 2)


def _estimate_json_bytes(value: Any) -> int:
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        payload = str(value)
    return len(payload.encode("utf-8", errors="ignore"))


def _read_linux_proc_status_metrics() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    status_path = "/proc/self/status"
    if not os.path.exists(status_path):
        return metrics
    try:
        with open(status_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    metrics["rss_kb"] = int(parts[1]) if len(parts) >= 2 else None
                elif line.startswith("VmSize:"):
                    parts = line.split()
                    metrics["vmsize_kb"] = int(parts[1]) if len(parts) >= 2 else None
                elif line.startswith("Threads:"):
                    parts = line.split()
                    metrics["proc_threads"] = int(parts[1]) if len(parts) >= 2 else None
        return metrics
    except Exception:
        return metrics


def _read_open_fd_count() -> Optional[int]:
    fd_dir = "/proc/self/fd"
    if not os.path.isdir(fd_dir):
        return None
    try:
        return len(os.listdir(fd_dir))
    except Exception:
        return None


def _read_windows_process_memory() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    if sys.platform != "win32":
        return metrics
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.WinDLL("psapi")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_current = kernel32.GetCurrentProcess
        get_current.restype = wintypes.HANDLE
        get_mem = psapi.GetProcessMemoryInfo
        get_mem.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        get_mem.restype = wintypes.BOOL

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if not get_mem(get_current(), ctypes.byref(counters), counters.cb):
            return metrics
        metrics["rss_kb"] = int(counters.WorkingSetSize // 1024)
        metrics["vmsize_kb"] = int(counters.PagefileUsage // 1024)
        metrics["peak_rss_kb"] = int(counters.PeakWorkingSetSize // 1024)
        metrics["source"] = "windows_psapi"
        return metrics
    except Exception:
        return metrics


def _read_resource_rusage_memory() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # Linux: ru_maxrss is KB; macOS: bytes
        maxrss = int(getattr(usage, "ru_maxrss", 0) or 0)
        if sys.platform == "darwin":
            metrics["peak_rss_kb"] = int(maxrss // 1024) if maxrss else None
        else:
            metrics["peak_rss_kb"] = maxrss or None
        metrics["source"] = "resource.getrusage"
        return metrics
    except Exception:
        return metrics


def _read_process_memory() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "rss_kb": None,
        "vmsize_kb": None,
        "peak_rss_kb": None,
        "proc_threads": None,
        "source": None,
    }
    linux = _read_linux_proc_status_metrics()
    if linux:
        metrics.update(linux)
        metrics["source"] = "procfs"
        return metrics

    win = _read_windows_process_memory()
    if win.get("rss_kb") is not None:
        metrics.update(win)
        return metrics

    rusage = _read_resource_rusage_memory()
    if rusage:
        metrics.update({k: v for k, v in rusage.items() if v is not None})
        if not metrics.get("source"):
            metrics["source"] = rusage.get("source")
    return metrics


def _read_cgroup_memory_metrics() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "cgroup_memory_current_bytes": None,
        "cgroup_memory_max_bytes": None,
        "cgroup_memory_events": {},
    }
    memory_current_path = "/sys/fs/cgroup/memory.current"
    memory_max_path = "/sys/fs/cgroup/memory.max"
    memory_events_path = "/sys/fs/cgroup/memory.events"
    try:
        if os.path.exists(memory_current_path):
            raw = str(Path(memory_current_path).read_text(encoding="utf-8", errors="ignore") or "").strip()
            if raw.isdigit():
                metrics["cgroup_memory_current_bytes"] = int(raw)
    except Exception:
        pass
    try:
        if os.path.exists(memory_max_path):
            raw = str(Path(memory_max_path).read_text(encoding="utf-8", errors="ignore") or "").strip()
            if raw and raw.lower() != "max" and raw.isdigit():
                metrics["cgroup_memory_max_bytes"] = int(raw)
            elif raw.lower() == "max":
                metrics["cgroup_memory_max_bytes"] = None
    except Exception:
        pass
    try:
        if os.path.exists(memory_events_path):
            events: Dict[str, int] = {}
            for line in Path(memory_events_path).read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = str(line or "").strip().split()
                if len(parts) != 2:
                    continue
                try:
                    events[str(parts[0])] = int(parts[1])
                except Exception:
                    continue
            metrics["cgroup_memory_events"] = events
    except Exception:
        pass
    return metrics


def _snapshot_dict_footprint(name: str, store: Any, lock: Any = None) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "name": str(name),
        "items": 0,
        "sample_items": 0,
        "sample_bytes": 0,
        "approx_total_bytes": 0,
        "approx_total_mb": 0.0,
    }
    try:
        if lock is not None:
            with lock:
                items = int(len(store)) if hasattr(store, "__len__") else 0
                sample_values = (
                    list(islice(getattr(store, "values")(), _STORE_SAMPLE_ITEMS))
                    if hasattr(store, "values")
                    else []
                )
        else:
            items = int(len(store)) if hasattr(store, "__len__") else 0
            sample_values = (
                list(islice(getattr(store, "values")(), _STORE_SAMPLE_ITEMS))
                if hasattr(store, "values")
                else []
            )
    except Exception:
        return info

    sample_bytes = sum(_estimate_json_bytes(value) for value in sample_values)
    sample_count = len(sample_values)
    avg_bytes = int(sample_bytes / sample_count) if sample_count > 0 else 0
    approx_total = int(avg_bytes * items) if avg_bytes > 0 else 0
    info.update(
        {
            "items": items,
            "sample_items": sample_count,
            "sample_bytes": sample_bytes,
            "approx_total_bytes": approx_total,
            "approx_total_mb": _bytes_to_mb(approx_total) or 0.0,
        }
    )
    return info


def _resolve_job_store_module() -> Any:
    try:
        from app.services.generation_runtime import job_store

        return job_store
    except Exception:
        return sys.modules.get("app.services.generation_runtime.job_store")


def _collect_store_footprints() -> List[Dict[str, Any]]:
    footprints: List[Dict[str, Any]] = []
    job_store = _resolve_job_store_module()
    if job_store is not None:
        candidates = [
            ("image_job_store", getattr(job_store, "IMAGE_JOB_STORE", None), getattr(job_store, "IMAGE_JOB_LOCK", None)),
            ("video_job_store", getattr(job_store, "VIDEO_JOB_STORE", None), getattr(job_store, "VIDEO_JOB_LOCK", None)),
            ("generation_callback_store", getattr(job_store, "GENERATION_CALLBACK_STORE", None), getattr(job_store, "GENERATION_CALLBACK_LOCK", None)),
            ("generation_callback_async_inflight", getattr(job_store, "GENERATION_CALLBACK_ASYNC_INFLIGHT", None), getattr(job_store, "GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK", None)),
            ("generation_callback_no_match_cache", getattr(job_store, "GENERATION_CALLBACK_NO_MATCH_LOG_CACHE", None), getattr(job_store, "GENERATION_CALLBACK_NO_MATCH_LOG_LOCK", None)),
            ("webhook_replay_store", getattr(job_store, "WEBHOOK_REPLAY_STORE", None), getattr(job_store, "WEBHOOK_REPLAY_LOCK", None)),
            ("generation_job_pool_cache", getattr(job_store, "_GENERATION_JOB_POOL_CACHE", None), getattr(job_store, "_GENERATION_JOB_POOL_CACHE_LOCK", None)),
        ]
        for name, store, lock in candidates:
            if isinstance(store, dict):
                footprints.append(_snapshot_dict_footprint(name, store, lock))

    endpoints_module = sys.modules.get("app.api.endpoints")
    if endpoints_module is not None:
        analyze_store = getattr(endpoints_module, "_ANALYZE_SCENE_RECENT_TASKS", None)
        analyze_lock = getattr(endpoints_module, "_ANALYZE_SCENE_RECENT_TASKS_LOCK", None)
        if isinstance(analyze_store, dict):
            footprints.append(_snapshot_dict_footprint("analyze_scene_recent_tasks", analyze_store, analyze_lock))

    try:
        from app.services.task_manager import snapshot_async_task_store_footprint

        async_fp = snapshot_async_task_store_footprint(_STORE_SAMPLE_ITEMS)
        if isinstance(async_fp, dict):
            async_fp["approx_total_mb"] = _bytes_to_mb(async_fp.get("approx_total_bytes")) or 0.0
            footprints.append(async_fp)
    except Exception:
        pass

    footprints.sort(key=lambda item: int(item.get("approx_total_bytes") or 0), reverse=True)
    return footprints


def _collect_gc_stats() -> Dict[str, Any]:
    counts = list(gc.get_count())
    thresholds = list(gc.get_threshold())
    stats = []
    try:
        raw_stats = gc.get_stats()
        if isinstance(raw_stats, list):
            stats = raw_stats
    except Exception:
        stats = []
    return {
        "enabled": bool(gc.isenabled()),
        "counts": counts,
        "thresholds": thresholds,
        "stats": stats,
        "garbage_objects": len(gc.garbage),
        "tracked_objects": len(gc.get_objects()),
        "freeze_count": int(getattr(gc, "get_freeze_count", lambda: 0)() or 0),
    }


def _collect_tracemalloc_top() -> Dict[str, Any]:
    tracing = bool(tracemalloc.is_tracing())
    out: Dict[str, Any] = {
        "tracing": tracing,
        "top": [],
        "traced_current_mb": None,
        "traced_peak_mb": None,
    }
    if not tracing:
        return out
    try:
        current, peak = tracemalloc.get_traced_memory()
        out["traced_current_mb"] = _bytes_to_mb(current)
        out["traced_peak_mb"] = _bytes_to_mb(peak)
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")[:_TRACEMALLOC_TOP]
        top: List[Dict[str, Any]] = []
        for stat in stats:
            frame = stat.traceback[0] if stat.traceback else None
            top.append(
                {
                    "location": (
                        f"{getattr(frame, 'filename', '')}:{getattr(frame, 'lineno', 0)}"
                        if frame
                        else ""
                    ),
                    "size_bytes": int(getattr(stat, "size", 0) or 0),
                    "size_mb": _bytes_to_mb(getattr(stat, "size", 0)) or 0.0,
                    "count": int(getattr(stat, "count", 0) or 0),
                }
            )
        out["top"] = top
    except Exception as exc:
        out["error"] = str(exc)
    return out


def _try_malloc_trim() -> bool:
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        trim = getattr(libc, "malloc_trim", None)
        if not callable(trim):
            return False
        return bool(trim(0))
    except Exception:
        return False


def _prune_generation_caches() -> Dict[str, Any]:
    result = {
        "image_jobs_pruned": False,
        "video_jobs_pruned": False,
        "async_tasks_evicted": False,
        "errors": [],
    }
    job_store = _resolve_job_store_module()
    if job_store is not None:
        try:
            image_lock = getattr(job_store, "IMAGE_JOB_LOCK", None)
            prune_image = getattr(job_store, "_prune_image_jobs_locked", None)
            if image_lock is not None and callable(prune_image):
                with image_lock:
                    prune_image()
                result["image_jobs_pruned"] = True
        except Exception as exc:
            result["errors"].append(f"image_prune:{exc}")
        try:
            video_lock = getattr(job_store, "VIDEO_JOB_LOCK", None)
            prune_video = getattr(job_store, "_prune_video_jobs_locked", None)
            if video_lock is not None and callable(prune_video):
                with video_lock:
                    prune_video()
                result["video_jobs_pruned"] = True
        except Exception as exc:
            result["errors"].append(f"video_prune:{exc}")
    try:
        from app.services.task_manager import snapshot_async_task_store_footprint

        snapshot_async_task_store_footprint(8)  # triggers stale eviction
        result["async_tasks_evicted"] = True
    except Exception as exc:
        result["errors"].append(f"async_evict:{exc}")
    return result


def _process_snapshot() -> Dict[str, Any]:
    mem = _read_process_memory()
    cgroup = _read_cgroup_memory_metrics()
    rss_kb = _safe_int(mem.get("rss_kb"))
    vmsize_kb = _safe_int(mem.get("vmsize_kb"))
    peak_rss_kb = _safe_int(mem.get("peak_rss_kb"))
    now_ts = time.time()
    return {
        "pid": os.getpid(),
        "timestamp": now_bj_iso(),
        "uptime_seconds": max(0, int(now_ts - _PROCESS_STARTED_UNIX_TS)),
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "threads_active": threading.active_count(),
        "open_fd": _read_open_fd_count(),
        "memory": {
            "rss_kb": rss_kb,
            "rss_mb": round((rss_kb or 0) / 1024.0, 2) if rss_kb is not None else None,
            "vmsize_kb": vmsize_kb,
            "vmsize_mb": round((vmsize_kb or 0) / 1024.0, 2) if vmsize_kb is not None else None,
            "peak_rss_kb": peak_rss_kb,
            "peak_rss_mb": round((peak_rss_kb or 0) / 1024.0, 2) if peak_rss_kb is not None else None,
            "source": mem.get("source"),
            "proc_threads": mem.get("proc_threads"),
        },
        "cgroup": {
            "current_bytes": cgroup.get("cgroup_memory_current_bytes"),
            "current_mb": _bytes_to_mb(cgroup.get("cgroup_memory_current_bytes")),
            "max_bytes": cgroup.get("cgroup_memory_max_bytes"),
            "max_mb": _bytes_to_mb(cgroup.get("cgroup_memory_max_bytes")),
            "events": cgroup.get("cgroup_memory_events") or {},
            "usage_ratio": (
                round(
                    float(cgroup["cgroup_memory_current_bytes"])
                    / float(cgroup["cgroup_memory_max_bytes"]),
                    4,
                )
                if cgroup.get("cgroup_memory_current_bytes") is not None
                and cgroup.get("cgroup_memory_max_bytes")
                else None
            ),
        },
        "render": {
            "service_id": os.getenv("RENDER_SERVICE_ID", ""),
            "instance_id": os.getenv("RENDER_INSTANCE_ID", ""),
            "git_commit": os.getenv("RENDER_GIT_COMMIT", ""),
        },
    }


def collect_memory_stats(*, include_tracemalloc: bool = True) -> Dict[str, Any]:
    process = _process_snapshot()
    stores = _collect_store_footprints()
    store_total_bytes = sum(int(item.get("approx_total_bytes") or 0) for item in stores)
    payload = {
        **process,
        "gc": _collect_gc_stats(),
        "stores": {
            "items": stores,
            "approx_total_bytes": store_total_bytes,
            "approx_total_mb": _bytes_to_mb(store_total_bytes) or 0.0,
        },
        "analysis": _build_analysis(process, stores),
    }
    if include_tracemalloc:
        payload["tracemalloc"] = _collect_tracemalloc_top()
    return payload


def _build_analysis(process: Dict[str, Any], stores: List[Dict[str, Any]]) -> Dict[str, Any]:
    tips: List[str] = []
    rss_mb = ((process.get("memory") or {}).get("rss_mb"))
    cgroup = process.get("cgroup") or {}
    usage_ratio = cgroup.get("usage_ratio")
    top_store = stores[0] if stores else None

    if rss_mb is not None and rss_mb >= 1500:
        tips.append("进程 RSS 较高（≥1.5GB），建议检查生成任务缓存与回调 inflight。")
    if usage_ratio is not None and usage_ratio >= 0.85:
        tips.append("cgroup 内存使用率 ≥85%，接近容器上限，优先执行回收。")
    if top_store and int(top_store.get("approx_total_bytes") or 0) >= 32 * 1024 * 1024:
        tips.append(
            f"最大内存估算 store 为 {top_store.get('name')} "
            f"（约 {top_store.get('approx_total_mb')} MB / {top_store.get('items')} 条）。"
        )
    gc_info = None
    try:
        gc_info = _collect_gc_stats()
        if int(gc_info.get("garbage_objects") or 0) > 0:
            tips.append(f"gc.garbage 仍有 {gc_info.get('garbage_objects')} 个不可回收对象（可能存在循环引用）。")
    except Exception:
        pass
    if not tips:
        tips.append("当前内存指标未见明显异常。可定期刷新观察 RSS 与 store 增长趋势。")

    return {
        "tips": tips,
        "top_store": top_store,
        "pressure": (
            "high"
            if (usage_ratio is not None and usage_ratio >= 0.85)
            or (rss_mb is not None and rss_mb >= 2000)
            else "elevated"
            if (usage_ratio is not None and usage_ratio >= 0.7)
            or (rss_mb is not None and rss_mb >= 1200)
            else "normal"
        ),
    }


def run_memory_reclaim(
    *,
    prune_caches: bool = True,
    collect_gc: bool = True,
    malloc_trim: bool = True,
    generations: Optional[int] = None,
) -> Dict[str, Any]:
    before = collect_memory_stats(include_tracemalloc=False)
    actions: Dict[str, Any] = {
        "prune_caches": False,
        "gc_collected": None,
        "malloc_trim": False,
        "prune_detail": None,
    }
    if prune_caches:
        actions["prune_detail"] = _prune_generation_caches()
        actions["prune_caches"] = True
    if collect_gc:
        if generations is None:
            actions["gc_collected"] = int(gc.collect() or 0)
        else:
            actions["gc_collected"] = int(gc.collect(int(generations)) or 0)
    if malloc_trim:
        actions["malloc_trim"] = bool(_try_malloc_trim())
    after = collect_memory_stats(include_tracemalloc=False)

    before_rss = ((before.get("memory") or {}).get("rss_kb"))
    after_rss = ((after.get("memory") or {}).get("rss_kb"))
    delta_rss_kb = None
    if before_rss is not None and after_rss is not None:
        delta_rss_kb = int(after_rss) - int(before_rss)

    return {
        "timestamp": now_bj_iso(),
        "actions": actions,
        "before": before,
        "after": after,
        "delta": {
            "rss_kb": delta_rss_kb,
            "rss_mb": round((delta_rss_kb or 0) / 1024.0, 2) if delta_rss_kb is not None else None,
            "store_approx_mb": round(
                float((after.get("stores") or {}).get("approx_total_mb") or 0)
                - float((before.get("stores") or {}).get("approx_total_mb") or 0),
                2,
            ),
            "gc_tracked_objects": int((after.get("gc") or {}).get("tracked_objects") or 0)
            - int((before.get("gc") or {}).get("tracked_objects") or 0),
        },
    }


def set_tracemalloc_enabled(enabled: bool) -> Dict[str, Any]:
    currently = bool(tracemalloc.is_tracing())
    if enabled and not currently:
        frames = max(1, min(25, int(os.getenv("RUNTIME_DIAG_TRACEMALLOC_FRAMES", "8") or 8)))
        tracemalloc.start(frames)
    elif (not enabled) and currently:
        tracemalloc.stop()
    return {
        "tracing": bool(tracemalloc.is_tracing()),
        "changed": currently != bool(tracemalloc.is_tracing()),
        "timestamp": now_bj_iso(),
    }
