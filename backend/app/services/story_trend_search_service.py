from __future__ import annotations

import asyncio
import logging
import random
import re
import time
import warnings
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
DDG_INSTANT_URL = "https://api.duckduckgo.com/"
BING_HTML_URL = "https://cn.bing.com/search"
SERPER_API_URL = "https://google.serper.dev/search"
SEARXNG_INSTANCES = (
    "https://searx.be",
    "https://search.inetol.net",
    "https://searx.tiekoetter.com",
    "https://opnxng.com",
)
REPORT_MONTHS_WINDOW = 2
DEFAULT_LIMIT_PER_QUERY = 10
DEFAULT_INSTANT_TOPIC_LIMIT = 8
MIN_USEFUL_SNIPPET_LEN = 40
MAX_ENRICH_PER_QUERY = 2
SNIPPET_MAX_LEN = 480
SEARCH_CONCURRENCY_LIMIT = 3
SEARCH_QUERY_DELAY_SEC = 0.35
HTML_SEARCH_RETRIES = 3
DDGS_SEARCH_RETRIES = 2

GENERIC_SNIPPET_MARKERS = (
    "您在查找",
    "综合搜索帮你找到",
    "抖音综合搜索",
    "百度为您找到",
    "相关内容，支持在线观看",
)


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
    return score


def _rank_results_for_query(query: str, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not rows:
        return []
    return sorted(
        rows,
        key=lambda row: _result_relevance_score(
            query,
            str(row.get("title") or ""),
            str(row.get("snippet") or ""),
            str(row.get("url") or ""),
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


def _useful_result_count(rows: List[Dict[str, str]]) -> int:
    count = 0
    for row in rows:
        snippet = str(row.get("snippet") or "").strip()
        if snippet and not _is_low_quality_snippet(snippet):
            count += 1
    return count


def _merge_result_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    order: List[str] = []
    for row in rows:
        title = str(row.get("title") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title and not snippet:
            continue
        key = _normalize_url(url) if url else f"title:{title.lower()}"
        if key in merged:
            existing = merged[key]
            if len(snippet) > len(str(existing.get("snippet") or "")):
                existing["snippet"] = snippet
                if row.get("source"):
                    existing["source"] = row.get("source")
            if title and not existing.get("title"):
                existing["title"] = title
            if url and not existing.get("url"):
                existing["url"] = url
            if row.get("source") and not existing.get("source"):
                existing["source"] = row.get("source")
        else:
            merged[key] = {
                "query": str(row.get("query") or "").strip(),
                "title": title,
                "snippet": snippet,
                "url": url,
                "source": str(row.get("source") or "").strip(),
            }
            order.append(key)
    return [merged[key] for key in order]


def _search_ddgs_text(query: str, *, limit: int = DEFAULT_LIMIT_PER_QUERY) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return results
    for attempt in range(DDGS_SEARCH_RETRIES):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
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


def _fetch_page_summary(url: str, *, max_chars: int = SNIPPET_MAX_LEN) -> str:
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
        for tag_name, attrs in (
            ("meta", {"property": "og:description"}),
            ("meta", {"name": "description"}),
            ("meta", {"name": "twitter:description"}),
        ):
            tag = soup.find(tag_name, attrs=attrs)
            if tag and tag.get("content"):
                text_value = str(tag.get("content") or "").strip()
                if len(text_value) >= 20:
                    return text_value[:max_chars]
        article = soup.find("article") or soup.find("main") or soup.body
        if article:
            parts: List[str] = []
            for paragraph in article.find_all("p", limit=10):
                chunk = paragraph.get_text(" ", strip=True)
                if len(chunk) < 30:
                    continue
                parts.append(chunk)
                if sum(len(part) for part in parts) >= max_chars:
                    break
            if parts:
                return " ".join(parts)[:max_chars]
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
    queries: List[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = query.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    add(f"AI短剧 行业 趋势 分析 {period}")
    add(f"微短剧 市场 报告 AI生成 {period}")
    add("DataEye 微短剧 AI短剧 热度榜 行业")
    add("抖音 快手 红果 短剧 平台 对比 AI短剧")
    add(f"AI short drama industry trends market analysis {period}")
    add("AI generated micro drama genre trends audience preferences")
    add("短剧 题材 热门 趋势 反转 悬疑 AI")
    add("短剧 制作 成本 周期 AI生成 行业")
    add(f"AI短剧 监管 政策 平台 变化 {period}")
    add(f"短剧 商业化 投流 ROI 广告 {period}")
    return queries


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

    for label in months:
        year, month_num = _month_parts(label)
        add(f"{year}年{month_num}月 AI短剧 热榜 新上榜")
        add(f"AI短剧 排行榜 {year}年{month_num}月")
        add(f"微短剧 AI生成 热门 新片 {year}年{month_num}月")
        add(f"红果短剧 AI短剧 新上 {year}年{month_num}月")
        add(f"AI short drama trending ranking {year}-{month_num:02d}")
        add(f"抖音 短剧 热榜 AI {year}年{month_num}月")
    return queries


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


def resolve_serper_api_key() -> str:
    """Resolve Serper API key from system API settings, provider key pool, then env fallback."""
    env_key = str(getattr(settings, "SERPER_API_KEY", "") or "").strip()
    try:
        with SessionLocal() as db:
            row = (
                db.query(SystemAPISetting)
                .filter(
                    func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == "serper",
                    SystemAPISetting.category == "Tools",
                    SystemAPISetting.deprecated.is_(False),
                )
                .order_by(SystemAPISetting.is_active.desc(), SystemAPISetting.id.asc())
                .first()
            )
            fallback_key = str(getattr(row, "api_key", "") or "").strip() if row else ""

            pool_row = (
                db.query(ProviderKeyPool)
                .filter(func.lower(func.trim(func.coalesce(ProviderKeyPool.provider, ""))) == "serper")
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
            "[ai_short_drama_search] Failed to resolve Serper API key from system settings: %s",
            exc,
        )
    return env_key

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


async def _collect_backup_search_results(query: str, *, serper_api_key: str = "", limit_per_query: int) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    if str(serper_api_key or "").strip():
        serper_results = await asyncio.to_thread(_search_serper, query, api_key=serper_api_key, limit=limit_per_query)
        rows.extend(serper_results)
        if _useful_result_count(_merge_result_rows(rows)) >= limit_per_query:
            return rows

    bing_results = await asyncio.to_thread(_search_bing_html, query, limit=limit_per_query)
    rows.extend(bing_results)
    if _useful_result_count(_merge_result_rows(rows)) >= limit_per_query:
        return rows

    ddgs_results = await asyncio.to_thread(_search_ddgs_text, query, limit=limit_per_query)
    rows.extend(ddgs_results)
    if _useful_result_count(_merge_result_rows(rows)) >= limit_per_query:
        return rows

    searx_results = await asyncio.to_thread(_search_searxng, query, limit=limit_per_query)
    rows.extend(searx_results)
    if _useful_result_count(_merge_result_rows(rows)) >= limit_per_query:
        return rows

    serper_results = await asyncio.to_thread(_search_serper, query, api_key=serper_api_key, limit=limit_per_query)
    rows.extend(serper_results)
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
                timeout=25,
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


def _search_duckduckgo_instant(query: str, *, topic_limit: int = DEFAULT_INSTANT_TOPIC_LIMIT) -> str:
    try:
        response = requests.get(
            DDG_INSTANT_URL,
            params={
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
                "skip_disambig": 1,
            },
            timeout=25,
            headers=DEFAULT_HEADERS,
        )
        if response.status_code != 200:
            return ""
        data = response.json()
        parts: List[str] = []
        abstract = str(data.get("AbstractText") or "").strip()
        if abstract:
            parts.append(abstract)
        for item in (data.get("RelatedTopics") or [])[:topic_limit]:
            if isinstance(item, dict) and item.get("Text"):
                parts.append(str(item.get("Text") or "").strip())
        return "\n".join(parts).strip()
    except Exception as exc:
        logger.warning("[ai_short_drama_search] Instant search failed query=%s err=%s", query, exc)
        return ""


def _snippet_key(item: Dict[str, str]) -> str:
    return f"{item.get('url', '').strip().lower()}|{item.get('title', '').strip().lower()}"


async def _search_query_bundle(query: str, *, serper_api_key: str = "", limit_per_query: int) -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]]]:
    html_results, instant_text = await asyncio.gather(
        asyncio.to_thread(_search_duckduckgo_html, query, limit=limit_per_query),
        asyncio.to_thread(_search_duckduckgo_instant, query),
    )
    combined_rows = list(html_results)
    if _useful_result_count(_merge_result_rows(combined_rows)) < limit_per_query:
        backup_rows = await _collect_backup_search_results(query, serper_api_key=serper_api_key, limit_per_query=limit_per_query)
        combined_rows.extend(backup_rows)

    merged = _rank_results_for_query(query, _merge_result_rows(combined_rows))

    enriched_count = 0
    for item in merged:
        snippet = str(item.get("snippet") or "").strip()
        if enriched_count >= MAX_ENRICH_PER_QUERY:
            break
        if len(snippet) >= MIN_USEFUL_SNIPPET_LEN and not _is_low_quality_snippet(snippet):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        page_text = await asyncio.to_thread(_fetch_page_summary, url)
        if page_text and len(page_text) > len(snippet):
            item["snippet"] = page_text
            enriched_count += 1

    filtered: List[Dict[str, str]] = []
    fallback: List[Dict[str, str]] = []
    for item in merged:
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or "").strip()[:SNIPPET_MAX_LEN]
        if not title:
            continue
        row = {
            "query": query,
            "title": title,
            "snippet": snippet,
            "url": str(item.get("url") or "").strip(),
            "source": str(item.get("source") or "unknown").strip(),
        }
        if snippet and not _is_low_quality_snippet(snippet):
            filtered.append(row)
        else:
            fallback.append(row)

    if len(filtered) < limit_per_query:
        for row in fallback:
            if row in filtered:
                continue
            if not row.get("snippet") and instant_text:
                row["snippet"] = str(instant_text)[:SNIPPET_MAX_LEN]
            if row.get("snippet"):
                filtered.append(row)
            if len(filtered) >= limit_per_query:
                break

    instant_note = {"query": query, "text": instant_text} if instant_text else None
    return filtered[:limit_per_query], instant_note


async def _collect_search_snippets_for_queries(
    queries: List[str],
    *,
    month_label: Optional[str] = None,
    limit_per_query: int = DEFAULT_LIMIT_PER_QUERY,
    months_window: int = REPORT_MONTHS_WINDOW,
    report_kind: str,
) -> Dict[str, Any]:
    anchor = (month_label or current_report_month_label()).strip()
    report_months = resolve_report_months(anchor, window=months_window)
    report_period = current_report_period_label(anchor)

    semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY_LIMIT)
    serper_api_key = resolve_serper_api_key()

    async def _bounded_search(query: str) -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]]]:
        async with semaphore:
            await asyncio.sleep(SEARCH_QUERY_DELAY_SEC)
            return await _search_query_bundle(query, serper_api_key=serper_api_key, limit_per_query=limit_per_query)

    tasks = [_bounded_search(query) for query in queries]
    bundles = await asyncio.gather(*tasks)

    snippets: List[Dict[str, str]] = []
    instant_notes: List[Dict[str, str]] = []
    seen_snippets: set[str] = set()
    seen_instant: set[str] = set()

    for html_results, instant_note in bundles:
        for item in html_results:
            key = _snippet_key(item)
            if key in seen_snippets:
                continue
            seen_snippets.add(key)
            snippets.append(item)
        if instant_note:
            note_key = f"{instant_note.get('query', '')}|{instant_note.get('text', '')[:120]}"
            if note_key not in seen_instant:
                seen_instant.add(note_key)
                instant_notes.append(instant_note)

    source_stats: Dict[str, int] = {}
    for item in snippets:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "unknown").strip() or "unknown"
        source_stats[source] = source_stats.get(source, 0) + 1

    return {
        "report_kind": report_kind,
        "report_month": anchor,
        "report_period": report_period,
        "report_months": report_months,
        "fetched_at": datetime.now(BJ_TZ).isoformat(),
        "queries": queries,
        "snippets": snippets,
        "instant_notes": instant_notes,
        "source_stats": source_stats,
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
        months_window=months_window,
        report_kind="industry_analysis",
    )


async def collect_trending_dramas_search_snippets(
    *,
    month_label: Optional[str] = None,
    limit_per_query: int = DEFAULT_LIMIT_PER_QUERY,
    months_window: int = REPORT_MONTHS_WINDOW,
) -> Dict[str, Any]:
    queries = build_trending_dramas_search_queries(month_label, months_window=months_window)
    return await _collect_search_snippets_for_queries(
        queries,
        month_label=month_label,
        limit_per_query=limit_per_query,
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
        months_window=months_window,
        report_kind="combined",
    )


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
    ]
    if target_list_size is not None:
        lines.append(f"Target List Size: up to {max(3, min(int(target_list_size or 12), 20))} dramas")
    lines.extend(["", "Web Search Snippets:"])
    for idx, item in enumerate(search_bundle.get("snippets") or [], start=1):
        if not isinstance(item, dict):
            continue
        snippet = str(item.get("snippet") or "").strip()
        if not snippet:
            continue
        lines.extend(
            [
                f"[{idx}] Query: {item.get('query', '')}",
                f"Title: {item.get('title', '')}",
                f"Summary: {snippet}",
                f"URL: {item.get('url', '')}",
                "",
            ]
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
        analysis_focus="Industry-wide trends, platforms, genres, audience, production/AI-tech, monetization, and creator opportunities across the full report period.",
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
        analysis_focus="Hottest and newly-charted AI short dramas within the report period.",
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
