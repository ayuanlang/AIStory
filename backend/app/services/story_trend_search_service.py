from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from sqlalchemy import func

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.all_models import ProviderKeyPool, SystemAPISetting


logger = logging.getLogger(__name__)

BJ_TZ = timezone(timedelta(hours=8))
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
DDG_HTML_URL = "https://html.duckduckgo.com/html/"
BING_HTML_URL = "https://cn.bing.com/search"
SERPER_API_URL = "https://google.serper.dev/search"
BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
TAVILY_SEARCH_API_URL = "https://api.tavily.com/search"
SEARXNG_INSTANCES = (
    "https://searx.be",
    "https://search.inetol.net",
    "https://searx.tiekoetter.com",
    "https://opnxng.com",
)
REPORT_MONTHS_WINDOW = 2
DEFAULT_LIMIT_PER_QUERY = 10
MIN_USEFUL_SNIPPET_LEN = 40
MAX_ENRICH_PER_QUERY = 5
SNIPPET_MAX_LEN = 800
EXCERPT_MAX_LEN = 2000
# Skip re-fetch when SERP/raw text is already dense enough (unless always-enrich).
ENRICH_SKIP_MIN_CHARS = 360
SEARCH_CONCURRENCY_LIMIT = 3
SEARCH_QUERY_DELAY_SEC = 0.35
HTML_SEARCH_RETRIES = 2
DDG_HTML_SEARCH_TIMEOUT_SEC = 8
DDGS_SEARCH_RETRIES = 2
PRIORITY_TIER_P0 = 40
PRIORITY_TIER_P1 = 20


def _cfg_int(name: str, default: int) -> int:
    raw = getattr(settings, name, None)
    if raw is None or raw == "":
        raw = os.getenv(name, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _cfg_bool(name: str, default: bool = True) -> bool:
    raw = getattr(settings, name, None)
    if raw is None or raw == "":
        env = os.getenv(name, "")
        if env == "":
            return bool(default)
        raw = env
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def resolve_snippet_max_len() -> int:
    return max(200, _cfg_int("SEARCH_SNIPPET_MAX_LEN", SNIPPET_MAX_LEN))


def resolve_excerpt_max_len() -> int:
    return max(400, _cfg_int("SEARCH_EXCERPT_MAX_LEN", EXCERPT_MAX_LEN))


def resolve_enrich_top_k(default: Optional[int] = None) -> int:
    fallback = MAX_ENRICH_PER_QUERY if default is None else int(default)
    return max(0, _cfg_int("SEARCH_ENRICH_TOP_K", fallback))


def resolve_always_enrich_top_k() -> bool:
    return _cfg_bool("SEARCH_ALWAYS_ENRICH_TOP_K", True)
SEARCH_BACKEND_ALIASES = {
    "serper": "serper",
    "brave": "brave",
    "brave_search": "brave",
    "tavily": "tavily",
    "tavily_ai": "tavily",
    "ddg": "ddg_html",
    "ddg_html": "ddg_html",
    "duckduckgo": "ddg_html",
    "duckduckgo_html": "ddg_html",
    "ddgs": "ddgs",
    "bing": "bing_html",
    "bing_html": "bing_html",
    "searx": "searxng",
    "searxng": "searxng",
}
API_KEY_SEARCH_BACKENDS = frozenset({"serper", "brave", "tavily"})
DEFAULT_SEARCH_BACKENDS_CLOUD = ("serper", "brave", "tavily", "ddgs", "bing_html", "searxng")
DEFAULT_SEARCH_BACKENDS_LOCAL = ("serper", "brave", "tavily", "ddg_html", "ddgs", "bing_html", "searxng")


def _is_cloud_runtime() -> bool:
    return bool(os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("FLY_APP_NAME"))


def _ddg_html_search_enabled() -> bool:
    explicit = str(getattr(settings, "DISABLE_DDG_HTML_SEARCH", "") or os.getenv("DISABLE_DDG_HTML_SEARCH", "") or "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return False
    if explicit in {"0", "false", "no", "off"}:
        return True
    return not _is_cloud_runtime()


def _normalize_search_backend_name(raw_name: str) -> str:
    key = str(raw_name or "").strip().lower()
    return SEARCH_BACKEND_ALIASES.get(key, key)


def resolve_search_backend_chain(*, search_api_keys: Optional[Dict[str, str]] = None) -> List[str]:
    """Return ordered search backends for the current runtime."""
    keys = search_api_keys or resolve_search_api_keys()
    raw = str(getattr(settings, "SEARCH_BACKENDS", "") or os.getenv("SEARCH_BACKENDS", "") or "").strip()
    if raw:
        chain: List[str] = []
        seen: set[str] = set()
        for item in raw.split(","):
            backend = _normalize_search_backend_name(item)
            if backend and backend not in seen:
                seen.add(backend)
                chain.append(backend)
        if chain:
            return _filter_search_backend_chain(chain, keys)

    chain = list(DEFAULT_SEARCH_BACKENDS_CLOUD if _is_cloud_runtime() else DEFAULT_SEARCH_BACKENDS_LOCAL)
    if not _ddg_html_search_enabled():
        chain = [backend for backend in chain if backend != "ddg_html"]
    return _filter_search_backend_chain(chain, keys)


def _filter_search_backend_chain(chain: List[str], search_api_keys: Dict[str, str]) -> List[str]:
    filtered: List[str] = []
    for backend in chain:
        if backend in API_KEY_SEARCH_BACKENDS and not str(search_api_keys.get(backend) or "").strip():
            continue
        filtered.append(backend)
    return filtered


def _fallback_snippet_text(title: str, snippet: str, url: str = "") -> str:
    text = str(snippet or "").strip()
    if text and not _looks_like_url_only(text):
        return text
    title_text = str(title or "").strip()
    if title_text and not _looks_like_url_only(title_text):
        return title_text
    return ""


_URL_ONLY_PATTERN = re.compile(
    r"^(?:https?://|www\.)[\w\.-]+(?:/[^\s]*)?$",
    re.I,
)


def _looks_like_url_only(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return True
    if _URL_ONLY_PATTERN.match(text):
        return True
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "www.")) and len(text.split()) <= 1:
        return True
    if "://" in lowered:
        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        if cjk_count < 8 and len(text) < 160:
            return True
    if re.fullmatch(r"[\w\.-]+(?:/[\w\.%-]+)+", text) and len(text) < 120:
        return True
    return False


GENERIC_SNIPPET_MARKERS = (
    "您在查找",
    "综合搜索帮你找到",
    "抖音综合搜索",
    "百度为您找到",
    "相关内容，支持在线观看",
    "点击观看",
    "立即播放",
    "在线观看",
    "视频页面",
    "搜索结果",
    "综合搜索",
    "为您找到相关",
    "bilibili.com",
    "douyin.com",
    "ixigua.com",
    "v.qq.com",
    "youku.com",
    "mgtv.com",
)


def is_informative_search_snippet(snippet: str, *, title: str = "", url: str = "") -> bool:
    """Return True when snippet carries narrative substance (not link/title-only noise)."""
    return _is_informative_snippet(snippet, title=title, url=url)


def _is_informative_snippet(snippet: str, *, title: str = "", url: str = "") -> bool:
    text = str(snippet or "").strip()
    if not text or _looks_like_url_only(text):
        return False
    if text == str(title or "").strip() and _looks_like_url_only(str(url or "")):
        return False
    if _is_low_quality_snippet(text):
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk_count >= 12:
        return True
    if len(text) >= MIN_USEFUL_SNIPPET_LEN and cjk_count >= 6:
        return True
    word_count = len(re.findall(r"[a-zA-Z]{3,}", text))
    if len(text) >= MIN_USEFUL_SNIPPET_LEN and word_count >= 5:
        return True
    return len(text) >= MIN_USEFUL_SNIPPET_LEN


DRAMA_RELEVANCE_KEYWORDS = (
    "短剧",
    "微短剧",
    "ai短剧",
    "漫剧",
    "热榜",
    "排行榜",
    "行业",
    "趋势",
    "题材",
    "桥段",
    "名场面",
    "短 drama",
    "short drama",
    "micro drama",
)

IRRELEVANT_HOST_MARKERS = (
    "chatgpt.com",
    "openai.com",
    "zhihu.com",
    "zhidao.baidu.com",
    "douyin.com/search",
    "reddit.com",
    "wikipedia.org",
    "japan-ai.co.jp",
)


def _tokenize_query(query: str) -> List[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", str(query or "").lower())
    return [token for token in tokens if token not in {"ai", "the", "and", "for", "with"}]


def _result_relevance_score(query: str, title: str, snippet: str, url: str = "") -> int:
    haystack = f"{title} {snippet} {url}".lower()
    score = 0
    for token in _tokenize_query(query):
        if token in haystack:
            score += 4
    for keyword in DRAMA_RELEVANCE_KEYWORDS:
        if keyword.lower() in haystack:
            score += 3
    if "ai" in query.lower() and "ai" in haystack and ("短剧" in haystack or "drama" in haystack):
        score += 4
    for marker in IRRELEVANT_HOST_MARKERS:
        if marker in haystack:
            score -= 12
    if _is_low_quality_snippet(snippet):
        score -= 8
    if _looks_like_url_only(snippet):
        score -= 20
    return score


EVIDENCE_TAG_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("climax", ("高潮", "名场面", "反转", "climax", "iconic", "高潮戏")),
    ("hook", ("钩子", "开篇", "悬念", "hook", "开场", "吸睛")),
    ("dialogue", ("对白", "台词", "金句", "dialogue", "旁白", "独白")),
    ("trope", ("桥段", "套路", "母题", "trope", "类型梗")),
    ("market", ("热榜", "排行", "题材", "趋势", "数据", "热度", "榜单")),
    ("action", ("动作", "打斗", "走位", "动作戏", "fight", "blocking")),
)


def _infer_evidence_tags(title: str, evidence: str, query: str = "") -> List[str]:
    haystack = f"{title} {evidence} {query}".lower()
    tags: List[str] = []
    for tag, markers in EVIDENCE_TAG_RULES:
        if any(marker.lower() in haystack for marker in markers):
            tags.append(tag)
    return tags[:4]


def _priority_tier(score: int) -> str:
    if int(score or 0) >= PRIORITY_TIER_P0:
        return "P0"
    if int(score or 0) >= PRIORITY_TIER_P1:
        return "P1"
    return "P2"


def _result_priority_score(
    query: str,
    title: str,
    evidence: str,
    url: str = "",
    *,
    enriched: bool = False,
    source: str = "",
) -> int:
    """Composite priority for next-stage consumption (higher = feed first)."""
    text = str(evidence or "").strip()
    score = _result_relevance_score(query, title, text, url)
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    word_count = len(re.findall(r"[a-zA-Z]{3,}", text))
    score += min(28, cjk_count // 10)
    score += min(16, word_count // 8)
    score += min(24, len(text) // 100)
    if enriched:
        score += 12
    source_key = str(source or "").strip().lower()
    if source_key == "tavily":
        score += 6
    elif source_key in {"serper", "brave"}:
        score += 3
    if _is_informative_snippet(text, title=title, url=url):
        score += 8
    else:
        score -= 10
    host = str(url or "").lower()
    if any(marker in host for marker in ("douyin.com", "tiktok.com", "ixigua.com", "bilibili.com/video")):
        score -= 8
    tags = _infer_evidence_tags(title, text, query)
    score += min(12, len(tags) * 3)
    return score


def _row_evidence_text(row: Dict[str, Any]) -> str:
    excerpt = str(row.get("excerpt") or "").strip()
    snippet = str(row.get("snippet") or "").strip()
    if excerpt and (not snippet or len(excerpt) >= len(snippet)):
        return excerpt
    return snippet or excerpt


def _attach_priority_fields(row: Dict[str, Any], *, query: str = "") -> Dict[str, Any]:
    title = str(row.get("title") or "").strip()
    url = str(row.get("url") or "").strip()
    evidence = _row_evidence_text(row)
    enriched = str(row.get("enriched") or "").strip() in {"1", "true", "True", "yes"}
    source = str(row.get("source") or "").strip()
    q = str(query or row.get("query") or "").strip()
    priority = _result_priority_score(
        q,
        title,
        evidence,
        url,
        enriched=enriched,
        source=source,
    )
    tags = _infer_evidence_tags(title, evidence, q)
    row["priority"] = priority
    row["priority_tier"] = _priority_tier(priority)
    row["evidence_tags"] = tags
    if evidence and not str(row.get("excerpt") or "").strip() and len(evidence) > len(str(row.get("snippet") or "")):
        row["excerpt"] = evidence
    return row


def _rank_results_for_query(query: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    return sorted(
        rows,
        key=lambda row: _result_priority_score(
            query,
            str(row.get("title") or ""),
            _row_evidence_text(row),
            str(row.get("url") or ""),
            enriched=str(row.get("enriched") or "").strip() in {"1", "true", "True"},
            source=str(row.get("source") or ""),
        ),
        reverse=True,
    )


def _sort_snippets_by_priority(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not snippets:
        return []
    decorated: List[Dict[str, Any]] = []
    for row in snippets:
        if not isinstance(row, dict):
            continue
        decorated.append(_attach_priority_fields(dict(row)))
    return sorted(
        decorated,
        key=lambda row: (
            int(row.get("priority") or 0),
            len(_row_evidence_text(row)),
        ),
        reverse=True,
    )



def _is_low_quality_snippet(snippet: str) -> bool:
    text = str(snippet or "").strip()
    if not text:
        return True
    if len(text) < MIN_USEFUL_SNIPPET_LEN:
        return True
    return any(marker in text for marker in GENERIC_SNIPPET_MARKERS)


def _normalize_url(url: str) -> str:
    return str(url or "").strip().lower().rstrip("/")


def _useful_result_count(rows: List[Dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        evidence = _row_evidence_text(row)
        if evidence and not _is_low_quality_snippet(evidence):
            count += 1
    return count


def _merge_result_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        title = str(row.get("title") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        excerpt = str(row.get("excerpt") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title and not snippet and not excerpt:
            continue
        key = _normalize_url(url) if url else f"title:{title.lower()}"
        if key in merged:
            existing = merged[key]
            if len(snippet) > len(str(existing.get("snippet") or "")):
                existing["snippet"] = snippet
                if row.get("source"):
                    existing["source"] = row.get("source")
            if len(excerpt) > len(str(existing.get("excerpt") or "")):
                existing["excerpt"] = excerpt
            if title and not existing.get("title"):
                existing["title"] = title
            if url and not existing.get("url"):
                existing["url"] = url
            if row.get("source") and not existing.get("source"):
                existing["source"] = row.get("source")
            if row.get("enriched") and not existing.get("enriched"):
                existing["enriched"] = row.get("enriched")
        else:
            merged[key] = {
                "query": str(row.get("query") or "").strip(),
                "title": title,
                "snippet": snippet,
                "excerpt": excerpt,
                "url": url,
                "source": str(row.get("source") or "").strip(),
                "enriched": row.get("enriched") or "",
            }
            order.append(key)
    return [merged[key] for key in order]


def _load_ddgs_client():
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # legacy shim; emits rename warning
            return DDGS
        except ImportError:
            return None


def _search_ddgs_text(query: str, *, limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    DDGS = _load_ddgs_client()
    if DDGS is None:
        return results
    for attempt in range(DDGS_SEARCH_RETRIES):
        try:
            with DDGS() as ddgs:
                rows = list(ddgs.text(query, max_results=limit))
            for row in rows:
                title = str(row.get("title") or "").strip()
                body = str(row.get("body") or "").strip()
                url = str(row.get("href") or "").strip()
                if title or body:
                    results.append({"query": query, "title": title, "snippet": body, "url": url, "source": "ddgs"})
            if results:
                break
        except Exception as exc:
            logger.warning(
                "[ai_short_drama_search] DDGS search failed query=%s attempt=%s err=%s",
                query,
                attempt + 1,
                exc,
            )
            time.sleep(1.0 * (attempt + 1))
    return results


def _clean_extracted_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned


def _fetch_page_summary(url: str, *, max_chars: Optional[int] = None) -> str:
    """Fetch usable page body/meta text for evidence packing (not link-only)."""
    limit = int(max_chars or resolve_excerpt_max_len())
    if not url.startswith(("http://", "https://")):
        return ""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=12, allow_redirects=True)
        if response.status_code != 200:
            return ""
        content_type = str(response.headers.get("content-type") or "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for junk in soup(["script", "style", "noscript", "svg", "iframe"]):
            junk.decompose()
        for junk in soup.find_all(["nav", "footer", "aside", "form", "header"]):
            junk.decompose()

        meta_text = ""
        for tag_name, attrs in (
            ("meta", {"property": "og:description"}),
            ("meta", {"name": "description"}),
            ("meta", {"name": "twitter:description"}),
        ):
            tag = soup.find(tag_name, attrs=attrs)
            if tag and tag.get("content"):
                text_value = _clean_extracted_text(str(tag.get("content") or ""))
                if len(text_value) >= 20:
                    meta_text = text_value
                    break

        article = soup.find("article") or soup.find("main") or soup.body
        parts: List[str] = []
        if article:
            for paragraph in article.find_all(["p", "li"], limit=40):
                chunk = _clean_extracted_text(paragraph.get_text(" ", strip=True))
                if len(chunk) < 24:
                    continue
                if _is_low_quality_snippet(chunk) and len(chunk) < 80:
                    continue
                parts.append(chunk)
                if sum(len(part) for part in parts) >= limit:
                    break
        body_text = _clean_extracted_text(" ".join(parts))[:limit]
        if body_text and _is_informative_snippet(body_text, url=url):
            return body_text
        if meta_text and (not body_text or len(meta_text) > len(body_text)):
            return meta_text[:limit]
        return body_text or meta_text[:limit]
    except Exception as exc:
        logger.debug("[ai_short_drama_search] page fetch failed url=%s err=%s", url, exc)
    return ""


def current_report_month_label() -> str:
    return datetime.now(BJ_TZ).strftime("%Y-%m")


def _shift_month_label(label: str, offset: int) -> str:
    try:
        year_s, month_s = label.split("-", 1)
        year = int(year_s)
        month = int(month_s)
    except Exception:
        now = datetime.now(BJ_TZ)
        year, month = now.year, now.month
    month += offset
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}-{month:02d}"


def resolve_report_months(month_label: Optional[str] = None, *, window: int = REPORT_MONTHS_WINDOW) -> List[str]:
    anchor = (month_label or current_report_month_label()).strip()
    months: List[str] = []
    for offset in range(window - 1, -1, -1):
        months.append(_shift_month_label(anchor, -offset))
    return months


def current_report_period_label(month_label: Optional[str] = None) -> str:
    months = resolve_report_months(month_label)
    if len(months) <= 1:
        return months[0] if months else current_report_month_label()
    return f"{months[0]} ~ {months[-1]}"


def _month_parts(label: str) -> Tuple[str, int]:
    try:
        year, month = label.split("-", 1)
        return year, int(month)
    except Exception:
        now = datetime.now(BJ_TZ)
        return now.strftime("%Y"), now.month


def build_industry_analysis_search_queries(
    month_label: Optional[str] = None,
    *,
    months_window: int = REPORT_MONTHS_WINDOW,
) -> List[str]:
    period = current_report_period_label(month_label)
    months = resolve_report_months(month_label, window=months_window)
    queries: List[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = query.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    add(f"AI短剧 热榜 题材 变化 对比 {period}")
    add(f"微短剧 热榜 题材 趋势 {period}")
    add(f"短剧 热榜 新上榜 题材 {period}")
    add("DataEye 微短剧 热度榜 题材 排行")
    add("抖音 快手 红果 短剧 热榜 题材 对比")
    add(f"AI short drama hot list genre trends {period}")
    add("AI generated micro drama trending genres rising declining")
    for label in months:
        year, month_num = _month_parts(label)
        add(f"{year}年{month_num}月 短剧 热榜 题材 热门")
        add(f"{year}年{month_num}月 AI短剧 热榜 新题材")
        add(f"{year}年{month_num}月 微短剧 题材 升温 降温")
        add(f"短剧 热榜 悬疑 甜宠 复仇 逆袭 题材 {year}年{month_num}月")
    add("短剧 题材 热门 趋势 反转 悬疑 甜宠 AI")
    add(f"AI短剧 行业 热榜 变化 {period}")
    return queries


TRENDING_DRAMAS_LIMIT_PER_QUERY = max(DEFAULT_LIMIT_PER_QUERY, 12)
TRENDING_DRAMAS_MAX_QUERIES = 36


def build_trending_dramas_search_queries(
    month_label: Optional[str] = None,
    *,
    months_window: int = REPORT_MONTHS_WINDOW,
) -> List[str]:
    months = resolve_report_months(month_label, window=months_window)
    queries: List[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = query.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    def add_month_climax_pack(year: int, month_num: int) -> None:
        ym = f"{year}年{month_num}月"
        add(f"{ym} AI短剧 热榜 新上榜")
        add(f"AI短剧 排行榜 {ym}")
        add(f"微短剧 AI生成 热门 新片 {ym}")
        add(f"红果短剧 AI短剧 新上 {ym}")
        add(f"AI short drama trending ranking {year}-{month_num:02d}")
        add(f"抖音 短剧 热榜 AI {ym}")
        add(f"{ym} 短剧 热榜 名场面 高潮")
        add(f"{ym} AI短剧 爆款 经典名场面 对白")
        add(f"{ym} 微短剧 热榜 高潮场面 反转")
        add(f"{ym} 短剧 热门 经典镜头 动作场面")
        add(f"AI short drama {year}-{month_num:02d} iconic climax scene")

    for label in months:
        year, month_num = _month_parts(label)
        add_month_climax_pack(year, month_num)

    period = current_report_period_label(month_label)
    add(f"AI短剧 热榜 名场面 高潮 {period}")
    add(f"短剧 爆款 经典对白 名场面 {period}")
    add(f"微短剧 热门 高潮 反转 镜头 {period}")

    return queries[:TRENDING_DRAMAS_MAX_QUERIES]


def build_trending_search_queries(
    month_label: Optional[str] = None,
    *,
    months_window: int = REPORT_MONTHS_WINDOW,
) -> List[str]:
    return build_industry_analysis_search_queries(month_label, months_window=months_window) + build_trending_dramas_search_queries(
        month_label,
        months_window=months_window,
    )




def _search_bing_html(query: str, *, limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for attempt in range(HTML_SEARCH_RETRIES):
        try:
            response = requests.get(
                BING_HTML_URL,
                params={"q": query, "setlang": "zh-Hans"},
                timeout=25,
                headers=DEFAULT_HEADERS,
            )
            if response.status_code in {403, 429, 503}:
                time.sleep(1.2 * (attempt + 1))
                continue
            if response.status_code != 200:
                return results
            soup = BeautifulSoup(response.text, "html.parser")
            for item in soup.select("li.b_algo")[:limit]:
                h2 = item.select_one("h2")
                link = h2.select_one("a") if h2 else None
                caption = item.select_one(".b_caption p") or item.select_one(".b_algoSlug") or item.select_one("p")
                title = link.get_text(" ", strip=True) if link else (h2.get_text(" ", strip=True) if h2 else "")
                snippet = caption.get_text(" ", strip=True) if caption else ""
                url = str(link.get("href") or "").strip() if link else ""
                if title or snippet:
                    results.append(
                        {
                            "query": query,
                            "title": title,
                            "snippet": snippet,
                            "url": url,
                            "source": "bing_html",
                        }
                    )
            if results:
                break
        except Exception as exc:
            logger.warning(
                "[ai_short_drama_search] Bing HTML search failed query=%s attempt=%s err=%s",
                query,
                attempt + 1,
                exc,
            )
            time.sleep(1.0 * (attempt + 1))
    return results


def _search_searxng(query: str, *, limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for base in SEARXNG_INSTANCES:
        try:
            response = requests.get(
                f"{base.rstrip('/')}/search",
                params={"q": query, "format": "json", "language": "zh-CN"},
                timeout=15,
                headers=DEFAULT_HEADERS,
            )
            if response.status_code != 200:
                continue
            content_type = str(response.headers.get("content-type") or "").lower()
            if "application/json" not in content_type:
                continue
            data = response.json()
            for item in (data.get("results") or [])[:limit]:
                title = str(item.get("title") or "").strip()
                snippet = str(item.get("content") or "").strip()
                url = str(item.get("url") or "").strip()
                if title or snippet:
                    results.append(
                        {
                            "query": query,
                            "title": title,
                            "snippet": snippet,
                            "url": url,
                            "source": "searxng",
                        }
                    )
            if results:
                break
        except Exception as exc:
            logger.debug(
                "[ai_short_drama_search] SearXNG search failed base=%s query=%s err=%s",
                base,
                query,
                exc,
            )
    return results




def _normalize_api_keys(value: Any) -> List[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    else:
        return []
    out: List[str] = []
    for item in raw_items:
        key = str(item or "").strip()
        if key and key not in out:
            out.append(key)
    return out


def resolve_tools_provider_api_key(provider: str, *, env_fallback: str = "") -> str:
    """Resolve Tools provider API key from provider key pool, system API row, then env."""
    provider_norm = str(provider or "").strip().lower()
    env_key = str(env_fallback or "").strip()
    if not provider_norm:
        return env_key
    try:
        with SessionLocal() as db:
            row = (
                db.query(SystemAPISetting)
                .filter(
                    func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm,
                    SystemAPISetting.category == "Tools",
                    SystemAPISetting.deprecated.is_(False),
                )
                .order_by(SystemAPISetting.is_active.desc(), SystemAPISetting.id.asc())
                .first()
            )
            fallback_key = str(getattr(row, "api_key", "") or "").strip() if row else ""

            pool_row = (
                db.query(ProviderKeyPool)
                .filter(func.lower(func.trim(func.coalesce(ProviderKeyPool.provider, ""))) == provider_norm)
                .first()
            )
            if pool_row and pool_row.api_keys:
                pooled = _normalize_api_keys(pool_row.api_keys)
                if pooled:
                    return random.choice(pooled)

            if fallback_key:
                return fallback_key
    except Exception as exc:
        logger.warning(
            "[ai_short_drama_search] Failed to resolve %s API key from system settings: %s",
            provider_norm,
            exc,
        )
    return env_key


def resolve_search_api_keys() -> Dict[str, str]:
    return {
        "serper": resolve_tools_provider_api_key("serper", env_fallback=str(getattr(settings, "SERPER_API_KEY", "") or "")),
        "brave": resolve_tools_provider_api_key("brave", env_fallback=str(getattr(settings, "BRAVE_SEARCH_API_KEY", "") or "")),
        "tavily": resolve_tools_provider_api_key("tavily", env_fallback=str(getattr(settings, "TAVILY_API_KEY", "") or "")),
    }


def resolve_serper_api_key() -> str:
    return resolve_search_api_keys().get("serper", "")

def _search_serper(query: str, *, api_key: str = "", limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, str]]:
    api_key = str(api_key or resolve_serper_api_key()).strip()
    if not api_key:
        return []
    results: List[Dict[str, str]] = []
    try:
        response = requests.post(
            SERPER_API_URL,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "gl": "cn", "hl": "zh-cn", "num": max(3, min(limit, 10))},
            timeout=20,
        )
        if response.status_code != 200:
            logger.warning(
                "[ai_short_drama_search] Serper search failed query=%s status=%s",
                query,
                response.status_code,
            )
            return results
        data = response.json()
        for item in (data.get("organic") or [])[:limit]:
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            url = str(item.get("link") or "").strip()
            if title or snippet:
                results.append(
                    {
                        "query": query,
                        "title": title,
                        "snippet": snippet,
                        "url": url,
                        "source": "serper",
                    }
                )
    except Exception as exc:
        logger.warning("[ai_short_drama_search] Serper search failed query=%s err=%s", query, exc)
    return results


def _search_brave(query: str, *, api_key: str = "", limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, str]]:
    api_key = str(api_key or resolve_search_api_keys().get("brave", "")).strip()
    if not api_key:
        return []
    results: List[Dict[str, str]] = []
    try:
        response = requests.get(
            BRAVE_SEARCH_API_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query,
                "count": max(3, min(limit, 20)),
                "search_lang": "zh-hans",
                "country": "CN",
                "extra_snippets": "true",
            },
            timeout=20,
        )
        if response.status_code != 200:
            logger.warning(
                "[ai_short_drama_search] Brave search failed query=%s status=%s",
                query,
                response.status_code,
            )
            return results
        data = response.json()
        web_results = data.get("web") if isinstance(data.get("web"), dict) else {}
        for item in (web_results.get("results") or [])[:limit]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("description") or "").strip()
            extra_snippets = item.get("extra_snippets") if isinstance(item.get("extra_snippets"), list) else []
            if not snippet and extra_snippets:
                snippet = " ".join(str(part or "").strip() for part in extra_snippets if str(part or "").strip())
            url = str(item.get("url") or "").strip()
            if title or snippet:
                results.append(
                    {
                        "query": query,
                        "title": title,
                        "snippet": snippet,
                        "url": url,
                        "source": "brave",
                    }
                )
    except Exception as exc:
        logger.warning("[ai_short_drama_search] Brave search failed query=%s err=%s", query, exc)
    return results


def _search_tavily(query: str, *, api_key: str = "", limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, Any]]:
    api_key = str(api_key or resolve_search_api_keys().get("tavily", "")).strip()
    if not api_key:
        return []
    results: List[Dict[str, Any]] = []
    depth = str(getattr(settings, "TAVILY_SEARCH_DEPTH", "") or os.getenv("TAVILY_SEARCH_DEPTH", "advanced") or "advanced").strip().lower()
    if depth not in {"basic", "advanced"}:
        depth = "advanced"
    include_raw = _cfg_bool("TAVILY_INCLUDE_RAW_CONTENT", True)
    excerpt_limit = resolve_excerpt_max_len()
    snippet_limit = resolve_snippet_max_len()
    try:
        response = requests.post(
            TAVILY_SEARCH_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "max_results": max(3, min(limit, 10)),
                "search_depth": depth,
                "topic": "general",
                "include_answer": False,
                "include_raw_content": include_raw,
            },
            timeout=35,
        )
        if response.status_code != 200:
            logger.warning(
                "[ai_short_drama_search] Tavily search failed query=%s status=%s",
                query,
                response.status_code,
            )
            return results
        data = response.json()
        for item in (data.get("results") or [])[:limit]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            content = _clean_extracted_text(str(item.get("content") or ""))
            raw = _clean_extracted_text(str(item.get("raw_content") or ""))
            url = str(item.get("url") or "").strip()
            excerpt = ""
            if raw and len(raw) > len(content):
                excerpt = raw[:excerpt_limit]
            elif content:
                excerpt = content[:excerpt_limit]
            snippet = (content or raw)[:snippet_limit]
            if title or snippet or excerpt:
                results.append(
                    {
                        "query": query,
                        "title": title,
                        "snippet": snippet,
                        "excerpt": excerpt,
                        "url": url,
                        "source": "tavily",
                        "enriched": "1" if raw and len(raw) >= ENRICH_SKIP_MIN_CHARS else "",
                    }
                )
    except Exception as exc:
        logger.warning("[ai_short_drama_search] Tavily search failed query=%s err=%s", query, exc)
    return results


def _increment_diag_counter(store: Dict[str, int], key: str, amount: int = 1) -> None:
    store[key] = int(store.get(key, 0) or 0) + int(amount or 0)


def _new_search_run_diagnostics() -> Dict[str, Any]:
    return {
        "backend_calls": {},
        "backend_raw_rows": {},
        "backend_useful_rows": {},
        "queries_with_results": 0,
        "queries_empty": 0,
        "query_backend_traces": [],
    }


async def _collect_search_results_for_query(
    query: str,
    *,
    search_api_keys: Optional[Dict[str, str]] = None,
    limit_per_query: int,
    backend_chain: Optional[List[str]] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    keys = search_api_keys or resolve_search_api_keys()
    chain = list(backend_chain or resolve_search_backend_chain(search_api_keys=keys))
    query_trace: List[Dict[str, Any]] = []

    backend_runners = {
        "serper": lambda: _search_serper(query, api_key=keys.get("serper", ""), limit=limit_per_query),
        "brave": lambda: _search_brave(query, api_key=keys.get("brave", ""), limit=limit_per_query),
        "tavily": lambda: _search_tavily(query, api_key=keys.get("tavily", ""), limit=limit_per_query),
        "ddg_html": lambda: _search_duckduckgo_html(query, limit=limit_per_query),
        "ddgs": lambda: _search_ddgs_text(query, limit=limit_per_query),
        "bing_html": lambda: _search_bing_html(query, limit=limit_per_query),
        "searxng": lambda: _search_searxng(query, limit=limit_per_query),
    }

    for backend in chain:
        runner = backend_runners.get(backend)
        if not runner:
            continue
        useful_before = _useful_result_count(_merge_result_rows(rows))
        started = time.perf_counter()
        batch = await asyncio.to_thread(runner)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        rows.extend(batch)
        merged_rows = _merge_result_rows(rows)
        useful_after = _useful_result_count(merged_rows)
        useful_added = max(0, useful_after - useful_before)
        trace_item = {
            "backend": backend,
            "raw_rows": len(batch),
            "useful_added": useful_added,
            "total_useful": useful_after,
            "elapsed_ms": elapsed_ms,
            "satisfied": useful_after >= limit_per_query,
        }
        query_trace.append(trace_item)
        if diagnostics is not None:
            _increment_diag_counter(diagnostics["backend_calls"], backend)
            _increment_diag_counter(diagnostics["backend_raw_rows"], backend, len(batch))
            if useful_added:
                _increment_diag_counter(diagnostics["backend_useful_rows"], backend, useful_added)
        logger.info(
            "[ai_short_drama_search] backend_result query=%s backend=%s raw_rows=%s useful_added=%s total_useful=%s/%s elapsed_ms=%s satisfied=%s",
            query,
            backend,
            len(batch),
            useful_added,
            useful_after,
            limit_per_query,
            elapsed_ms,
            useful_after >= limit_per_query,
        )
        if useful_after >= limit_per_query:
            break

    if diagnostics is not None:
        if rows:
            _increment_diag_counter(diagnostics, "queries_with_results")
        else:
            _increment_diag_counter(diagnostics, "queries_empty")
        diagnostics["query_backend_traces"].append({"query": query, "backends": query_trace})

    if not rows:
        logger.warning("[ai_short_drama_search] query_empty query=%s backends_tried=%s", query, [item["backend"] for item in query_trace])
    return rows

def _extract_html_result_item(item: Any, query: str) -> Optional[Dict[str, str]]:
    title_node = item.select_one(".result__title") or item.select_one("h2.result__title")
    snippet_node = (
        item.select_one(".result__snippet")
        or item.select_one("a.result__snippet")
        or item.select_one(".result__extras .result__snippet")
    )
    link_node = item.select_one("a.result__a") or item.select_one(".result__url")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
    url = ""
    if link_node:
        url = str(link_node.get("href") or link_node.get_text(" ", strip=True) or "").strip()
    if not title and not snippet:
        return None
    return {"query": query, "title": title, "snippet": snippet, "url": url, "source": "duckduckgo_html"}


def _search_duckduckgo_html(query: str, *, limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for attempt in range(HTML_SEARCH_RETRIES):
        try:
            response = requests.post(
                DDG_HTML_URL,
                data={"q": query},
                timeout=DDG_HTML_SEARCH_TIMEOUT_SEC,
                headers=DEFAULT_HEADERS,
            )
            if response.status_code in {403, 429, 503}:
                time.sleep(1.2 * (attempt + 1))
                continue
            if response.status_code != 200:
                return results
            soup = BeautifulSoup(response.text, "html.parser")
            for item in soup.select(".result")[: max(limit * 2, limit)]:
                parsed = _extract_html_result_item(item, query)
                if parsed:
                    results.append(parsed)
                if len(results) >= limit:
                    break
            if not results:
                for item in soup.select(".web-result")[:limit]:
                    parsed = _extract_html_result_item(item, query)
                    if parsed:
                        results.append(parsed)
            if results:
                break
        except Exception as exc:
            logger.warning(
                "[ai_short_drama_search] HTML search failed query=%s attempt=%s err=%s",
                query,
                attempt + 1,
                exc,
            )
            time.sleep(1.0 * (attempt + 1))
    return results


def _snippet_key(item: Dict[str, Any]) -> str:
    return f"{str(item.get('url') or '').strip().lower()}|{str(item.get('title') or '').strip().lower()}"


async def _search_query_bundle(
    query: str,
    *,
    search_api_keys: Optional[Dict[str, str]] = None,
    limit_per_query: int,
    backend_chain: Optional[List[str]] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    max_enrich_per_query: Optional[int] = None,
    require_informative_snippet: bool = False,
) -> List[Dict[str, Any]]:
    combined_rows = await _collect_search_results_for_query(
        query,
        search_api_keys=search_api_keys,
        limit_per_query=limit_per_query,
        backend_chain=backend_chain,
        diagnostics=diagnostics,
    )
    merged = _rank_results_for_query(query, _merge_result_rows(combined_rows))

    snippet_limit = resolve_snippet_max_len()
    excerpt_limit = resolve_excerpt_max_len()
    enrich_budget = resolve_enrich_top_k(
        MAX_ENRICH_PER_QUERY if max_enrich_per_query is None else max_enrich_per_query
    )
    always_enrich = resolve_always_enrich_top_k()
    enriched_count = 0
    for item in merged:
        if enriched_count >= enrich_budget:
            break
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        excerpt = str(item.get("excerpt") or "").strip()
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        existing = excerpt or snippet
        already_dense = (
            len(existing) >= ENRICH_SKIP_MIN_CHARS
            and _is_informative_snippet(existing, title=title, url=url)
        )
        if already_dense and not always_enrich:
            continue
        if already_dense and always_enrich and len(existing) >= min(excerpt_limit, 1200):
            item["enriched"] = item.get("enriched") or "1"
            continue
        page_text = await asyncio.to_thread(_fetch_page_summary, url, max_chars=excerpt_limit)
        enriched_count += 1
        if not page_text:
            continue
        if len(page_text) > len(excerpt):
            item["excerpt"] = page_text[:excerpt_limit]
        if len(page_text) > len(snippet):
            item["snippet"] = page_text[:snippet_limit]
        if _is_informative_snippet(page_text, title=title, url=url):
            item["enriched"] = "1"

    filtered: List[Dict[str, Any]] = []
    fallback: List[Dict[str, Any]] = []
    for item in merged:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title:
            continue
        excerpt = str(item.get("excerpt") or "").strip()[:excerpt_limit]
        snippet = str(item.get("snippet") or "").strip()
        evidence = _fallback_snippet_text(title, excerpt or snippet, url)[:excerpt_limit]
        if not evidence:
            continue
        row: Dict[str, Any] = {
            "query": query,
            "title": title,
            # Downstream historically reads `snippet`; store best available body text here.
            "snippet": evidence,
            "excerpt": excerpt or evidence,
            "url": url,
            "source": str(item.get("source") or "unknown").strip(),
            "enriched": str(item.get("enriched") or "").strip(),
        }
        _attach_priority_fields(row, query=query)
        if _is_informative_snippet(_row_evidence_text(row), title=title, url=url):
            filtered.append(row)
        elif not require_informative_snippet:
            fallback.append(row)

    ranked = _sort_snippets_by_priority(filtered)
    if not require_informative_snippet and len(ranked) < limit_per_query:
        for row in _sort_snippets_by_priority(fallback):
            if any(_snippet_key(row) == _snippet_key(existing) for existing in ranked):
                continue
            ranked.append(row)
            if len(ranked) >= limit_per_query:
                break

    return ranked[:limit_per_query]


async def _collect_search_snippets_for_queries(
    queries: List[str],
    *,
    month_label: Optional[str] = None,
    limit_per_query: int = DEFAULT_LIMIT_PER_QUERY,
    max_enrich_per_query: int = MAX_ENRICH_PER_QUERY,
    require_informative_snippet: bool = False,
    months_window: int = REPORT_MONTHS_WINDOW,
    report_kind: str,
) -> Dict[str, Any]:
    anchor = (month_label or current_report_month_label()).strip()
    report_months = resolve_report_months(anchor, window=months_window)
    report_period = current_report_period_label(anchor)

    semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY_LIMIT)
    search_api_keys = resolve_search_api_keys()
    backend_chain = resolve_search_backend_chain(search_api_keys=search_api_keys)
    diagnostics = _new_search_run_diagnostics()
    enabled_api_backends = [name for name in API_KEY_SEARCH_BACKENDS if str(search_api_keys.get(name) or "").strip()]
    missing_api_backends = [name for name in API_KEY_SEARCH_BACKENDS if name not in enabled_api_backends]
    logger.info(
        "[ai_short_drama_search] search backends report_kind=%s enabled_api=%s missing_api=%s backend_chain=%s cloud_runtime=%s limit_per_query=%s",
        report_kind,
        enabled_api_backends,
        missing_api_backends,
        backend_chain,
        _is_cloud_runtime(),
        limit_per_query,
    )
    if missing_api_backends:
        logger.warning(
            "[ai_short_drama_search] API search providers missing keys report_kind=%s providers=%s. "
            "Configure in Admin > 系统 API or set SERPER_API_KEY / BRAVE_SEARCH_API_KEY / TAVILY_API_KEY.",
            report_kind,
            missing_api_backends,
        )
    if "ddg_html" not in backend_chain:
        logger.info(
            "[ai_short_drama_search] DuckDuckGo HTML disabled report_kind=%s",
            report_kind,
        )

    async def _bounded_search(query: str) -> List[Dict[str, Any]]:
        async with semaphore:
            await asyncio.sleep(SEARCH_QUERY_DELAY_SEC)
            return await _search_query_bundle(
                query,
                search_api_keys=search_api_keys,
                limit_per_query=limit_per_query,
                backend_chain=backend_chain,
                diagnostics=diagnostics,
                max_enrich_per_query=max_enrich_per_query,
                require_informative_snippet=require_informative_snippet,
            )

    started_at = time.perf_counter()
    tasks = [_bounded_search(query) for query in queries]
    bundles = await asyncio.gather(*tasks)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)

    snippets: List[Dict[str, Any]] = []
    seen_snippets: set[str] = set()
    tier_stats: Dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}

    for html_results in bundles:
        for item in html_results:
            evidence = _row_evidence_text(item)
            if require_informative_snippet and not _is_informative_snippet(
                evidence,
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
            ):
                continue
            key = _snippet_key(item)
            if key in seen_snippets:
                continue
            seen_snippets.add(key)
            snippets.append(item)

    snippets = _sort_snippets_by_priority(snippets)
    source_stats: Dict[str, int] = {}
    for item in snippets:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "unknown").strip() or "unknown"
        source_stats[source] = source_stats.get(source, 0) + 1
        tier = str(item.get("priority_tier") or "P2").strip() or "P2"
        tier_stats[tier] = int(tier_stats.get(tier, 0) or 0) + 1

    logger.info(
        "[ai_short_drama_search] search complete report_kind=%s queries=%s snippets=%s elapsed_ms=%s "
        "queries_with_results=%s queries_empty=%s backend_calls=%s backend_raw_rows=%s backend_useful_rows=%s "
        "source_stats=%s tier_stats=%s enrich_top_k=%s",
        report_kind,
        len(queries),
        len(snippets),
        elapsed_ms,
        int(diagnostics.get("queries_with_results", 0) or 0),
        int(diagnostics.get("queries_empty", 0) or 0),
        diagnostics.get("backend_calls") or {},
        diagnostics.get("backend_raw_rows") or {},
        diagnostics.get("backend_useful_rows") or {},
        source_stats,
        tier_stats,
        max_enrich_per_query,
    )

    return {
        "report_kind": report_kind,
        "report_month": anchor,
        "report_period": report_period,
        "report_months": report_months,
        "fetched_at": datetime.now(BJ_TZ).isoformat(),
        "queries": queries,
        "snippets": snippets,
        "instant_notes": [],
        "source_stats": source_stats,
        "tier_stats": tier_stats,
        "search_diagnostics": {
            "elapsed_ms": elapsed_ms,
            "queries_with_results": int(diagnostics.get("queries_with_results", 0) or 0),
            "queries_empty": int(diagnostics.get("queries_empty", 0) or 0),
            "backend_calls": diagnostics.get("backend_calls") or {},
            "backend_raw_rows": diagnostics.get("backend_raw_rows") or {},
            "backend_useful_rows": diagnostics.get("backend_useful_rows") or {},
            "tier_stats": tier_stats,
            "enrich_top_k": max_enrich_per_query,
        },
    }


async def collect_industry_analysis_search_snippets(
    *,
    month_label: Optional[str] = None,
    limit_per_query: int = DEFAULT_LIMIT_PER_QUERY,
    months_window: int = REPORT_MONTHS_WINDOW,
) -> Dict[str, Any]:
    queries = build_industry_analysis_search_queries(month_label, months_window=months_window)
    return await _collect_search_snippets_for_queries(
        queries,
        month_label=month_label,
        limit_per_query=limit_per_query,
        max_enrich_per_query=resolve_enrich_top_k(MAX_ENRICH_PER_QUERY),
        require_informative_snippet=True,
        months_window=months_window,
        report_kind="industry_analysis",
    )


async def collect_trending_dramas_search_snippets(
    *,
    month_label: Optional[str] = None,
    limit_per_query: int = TRENDING_DRAMAS_LIMIT_PER_QUERY,
    months_window: int = REPORT_MONTHS_WINDOW,
) -> Dict[str, Any]:
    queries = build_trending_dramas_search_queries(month_label, months_window=months_window)
    return await _collect_search_snippets_for_queries(
        queries,
        month_label=month_label,
        limit_per_query=limit_per_query,
        max_enrich_per_query=resolve_enrich_top_k(MAX_ENRICH_PER_QUERY),
        require_informative_snippet=True,
        months_window=months_window,
        report_kind="trending_dramas",
    )


async def collect_trending_ai_short_drama_search_snippets(
    *,
    month_label: Optional[str] = None,
    limit_per_query: int = DEFAULT_LIMIT_PER_QUERY,
    months_window: int = REPORT_MONTHS_WINDOW,
) -> Dict[str, Any]:
    queries = build_trending_search_queries(month_label, months_window=months_window)
    return await _collect_search_snippets_for_queries(
        queries,
        month_label=month_label,
        limit_per_query=limit_per_query,
        max_enrich_per_query=resolve_enrich_top_k(MAX_ENRICH_PER_QUERY),
        require_informative_snippet=True,
        months_window=months_window,
        report_kind="combined",
    )


def format_search_evidence_lines(
    snippets: Any,
    *,
    include_url: bool = True,
    max_chars_per_item: Optional[int] = None,
    heading: str = "Web Search Evidence (priority-ordered):",
) -> List[str]:
    """Render ranked evidence blocks for the next LLM stage."""
    limit = int(max_chars_per_item or resolve_excerpt_max_len())
    lines: List[str] = [heading]
    ranked = _sort_snippets_by_priority([row for row in (snippets or []) if isinstance(row, dict)])
    rendered = 0
    for idx, item in enumerate(ranked, start=1):
        evidence = _row_evidence_text(item)[:limit]
        if not evidence:
            continue
        title = str(item.get("title") or "").strip()
        tier = str(item.get("priority_tier") or _priority_tier(int(item.get("priority") or 0))).strip() or "P2"
        priority = int(item.get("priority") or 0)
        tags = item.get("evidence_tags") or []
        if isinstance(tags, str):
            tag_text = tags.strip()
        else:
            tag_text = ",".join(str(tag).strip() for tag in tags if str(tag).strip())
        header = f"[{idx}] [{tier}] score={priority}"
        if tag_text:
            header = f"{header} tags={tag_text}"
        lines.extend(
            [
                header,
                f"Query: {item.get('query', '')}",
                f"Title: {title}",
                f"Evidence: {evidence}",
            ]
        )
        if include_url:
            url = str(item.get("url") or "").strip()
            if url:
                lines.append(f"URL: {url}")
        lines.append("")
        rendered += 1
    if rendered <= 0:
        lines.append("(No informative web evidence returned.)")
    return lines


def _format_search_bundle_context(
    search_bundle: Dict[str, Any],
    *,
    project_title: str = "",
    language: str = "",
    analysis_focus: str,
    target_list_size: Optional[int] = None,
) -> str:
    report_period = str(search_bundle.get("report_period") or current_report_period_label())
    report_months = search_bundle.get("report_months") or resolve_report_months()
    month_label = str(search_bundle.get("report_month") or current_report_month_label())
    lines = [
        f"Report Period: {report_period} (last {len(report_months)} months)",
        f"Report Months: {', '.join(report_months)}",
        f"Anchor Month: {month_label}",
        f"Project Title: {project_title or '(none)'}",
        f"Preferred Language: {language or 'zh'}",
        f"Analysis Focus: {analysis_focus}",
        "Consume evidence in priority order: P0 first, then P1, then P2. Prefer Evidence body over URLs.",
    ]
    if target_list_size is not None:
        lines.append(f"Target List Size: up to {max(3, min(int(target_list_size or 12), 20))} dramas")
    lines.append("")
    lines.extend(
        format_search_evidence_lines(
            search_bundle.get("snippets") or [],
            include_url=True,
        )
    )
    if search_bundle.get("instant_notes"):
        lines.append("")
        lines.append("Instant Search Notes:")
        for idx, note in enumerate(search_bundle.get("instant_notes") or [], start=1):
            if not isinstance(note, dict):
                continue
            lines.append(f"{idx}. [{note.get('query', '')}] {note.get('text', '')}")
    return "\n".join(lines).strip()


def build_industry_analysis_user_prompt(
    search_bundle: Dict[str, Any],
    *,
    project_title: str = "",
    language: str = "",
) -> str:
    return _format_search_bundle_context(
        search_bundle,
        project_title=project_title,
        language=language,
        analysis_focus="Hot-list churn and genre/theme shifts across the full report period: what genres rise, cool down, or newly dominate; hook/trope pattern changes; platform hot-list differences.",
    )


def build_trending_dramas_user_prompt(
    search_bundle: Dict[str, Any],
    *,
    project_title: str = "",
    language: str = "",
    limit: int = 12,
) -> str:
    return _format_search_bundle_context(
        search_bundle,
        project_title=project_title,
        language=language,
        analysis_focus="Hottest and newly-charted AI short dramas within the report period. For each title, prioritize climax and iconic scenes: visual moments, classic dialogue, action blocking, and emotional peak staging.",
        target_list_size=limit,
    )


def build_trending_ai_short_dramas_user_prompt(
    search_bundle: Dict[str, Any],
    *,
    project_title: str = "",
    language: str = "",
    limit: int = 12,
) -> str:
    return build_trending_dramas_user_prompt(
        search_bundle,
        project_title=project_title,
        language=language,
        limit=limit,
    )
