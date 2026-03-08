"""
AI助手 MCP 工具集 — 用于辅助系统API定价配置。

工具:
  1. exchange_rate   — 汇率兑换: 将外币金额转换为人民币(CNY)
  2. fetch_pricing   — 定价页面读取: 抓取供应商定价页面, 提取结构化内容

依赖: requests (已在 requirements.txt 中)
"""

import logging
import re
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pricing_tools")

# ── 常量 ──────────────────────────────────────────────────────────
_REQUEST_TIMEOUT = 20  # seconds

# 常见货币代码(供前端下拉和校验)
SUPPORTED_CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "KRW", "HKD", "TWD",
    "SGD", "AUD", "CAD", "CHF", "INR", "THB", "MYR",
]

# ── 1. 汇率兑换 ──────────────────────────────────────────────────
def fetch_exchange_rate(from_currency: str, to_currency: str = "CNY") -> Dict[str, Any]:
    """从公开API获取实时汇率。

    使用 exchangerate-api.com 免费端点(无需key)。
    返回: {"from": "USD", "to": "CNY", "rate": 7.25, "source": "..."}
    """
    from_cur = from_currency.strip().upper()
    to_cur = to_currency.strip().upper()

    if from_cur == to_cur:
        return {"from": from_cur, "to": to_cur, "rate": 1.0, "source": "identity"}

    # 优先使用 open.er-api.com (免费, 无需注册)
    errors = []
    for api_url, parser in _EXCHANGE_RATE_APIS:
        try:
            url = api_url.format(from_cur=from_cur, to_cur=to_cur)
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT, headers={"User-Agent": "AIStory-PricingTool/1.0"})
            if resp.status_code == 200:
                rate = parser(resp.json(), from_cur, to_cur)
                if rate and rate > 0:
                    return {"from": from_cur, "to": to_cur, "rate": round(rate, 6), "source": url.split("/")[2]}
        except Exception as e:
            errors.append(str(e))
            continue

    return {"from": from_cur, "to": to_cur, "rate": None, "error": f"Failed to fetch rate: {'; '.join(errors)}"}


def convert_currency(amount: float, from_currency: str, to_currency: str = "CNY") -> Dict[str, Any]:
    """将金额从外币转换为目标货币(默认CNY)。

    返回: {
        "from_currency": "USD", "to_currency": "CNY",
        "from_amount": 0.03, "to_amount": 0.2175,
        "rate": 7.25, "source": "..."
    }
    """
    rate_info = fetch_exchange_rate(from_currency, to_currency)
    rate = rate_info.get("rate")
    if rate is None:
        return {
            "from_currency": rate_info["from"],
            "to_currency": rate_info["to"],
            "from_amount": amount,
            "to_amount": None,
            "rate": None,
            "error": rate_info.get("error", "Exchange rate unavailable"),
        }

    converted = round(amount * rate, 6)
    return {
        "from_currency": rate_info["from"],
        "to_currency": rate_info["to"],
        "from_amount": amount,
        "to_amount": converted,
        "rate": rate,
        "source": rate_info.get("source", ""),
    }


# ── 汇率API列表(自动fallback) ─────────────────────────────────
def _parse_er_api(data: dict, from_cur: str, to_cur: str) -> Optional[float]:
    """Parser for open.er-api.com"""
    rates = data.get("rates") or {}
    return rates.get(to_cur)

def _parse_exchangerate_api(data: dict, from_cur: str, to_cur: str) -> Optional[float]:
    """Parser for open.exchangerate-api.com"""
    rates = data.get("rates") or {}
    return rates.get(to_cur)


_EXCHANGE_RATE_APIS = [
    # (url_template, parser_func)
    ("https://open.er-api.com/v6/latest/{from_cur}", _parse_er_api),
    ("https://open.exchangerate-api.com/v6/latest/{from_cur}", _parse_exchangerate_api),
]


# ── 2. 定价页面读取 ──────────────────────────────────────────────
def fetch_pricing_page(url: str, max_length: int = 30000) -> Dict[str, Any]:
    """抓取供应商定价页面内容。

    抓取给定URL的HTML页面，提取纯文本和结构化表格内容,
    用于后续AI解析定价信息。

    Args:
        url: 供应商定价页面URL
        max_length: 返回文本最大字符数(防止过大)

    Returns:
        {
            "url": "https://...",
            "title": "页面标题",
            "text_content": "纯文本内容(已清洗)",
            "tables": [...],  # 提取到的表格
            "content_length": 12345,
            "truncated": false
        }
    """
    if not url or not url.strip():
        return {"url": "", "error": "URL is required"}

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return {"url": url, "error": "URL must start with http:// or https://"}

    try:
        resp = requests.get(
            url,
            timeout=_REQUEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"url": url, "error": f"Failed to fetch page: {e}"}

    content_type = resp.headers.get("Content-Type", "")
    if "json" in content_type:
        # JSON API response — return as-is
        try:
            json_data = resp.json()
            text = _json_to_text(json_data)
            return {
                "url": url,
                "title": "",
                "text_content": text[:max_length],
                "tables": [],
                "content_length": len(text),
                "truncated": len(text) > max_length,
                "format": "json",
            }
        except Exception:
            pass

    # HTML content — extract text
    html = resp.text
    title = _extract_title(html)
    text = _html_to_text(html)
    tables = _extract_tables(html)

    # ---------- JS-rendered SPA fallback (Jina Reader) ----------
    # If direct fetch returned very little text but HTML was large,
    # the page is likely a JS-rendered SPA. Use Jina Reader as fallback.
    _MIN_USEFUL_TEXT_LEN = 200
    if len(text) < _MIN_USEFUL_TEXT_LEN and len(html) > 2000:
        try:
            jina_resp = requests.get(
                f"https://r.jina.ai/{url}",
                timeout=30,
                headers={
                    "Accept": "text/plain",
                    "X-Return-Format": "text",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            if jina_resp.status_code == 200 and len(jina_resp.text.strip()) > len(text):
                text = jina_resp.text.strip()
                if not title:
                    for _line in text.split("\n"):
                        _line = _line.strip().lstrip("# ").strip()
                        if _line:
                            title = _line[:120]
                            break
        except Exception:
            pass  # keep whatever we got from direct fetch
    # ---------- end SPA fallback ----------

    truncated = len(text) > max_length
    return {
        "url": url,
        "title": title,
        "text_content": text[:max_length],
        "tables": tables[:20],  # 最多20个表格
        "content_length": len(text),
        "truncated": truncated,
        "format": "html",
    }


# ── HTML解析工具(纯正则, 无需额外依赖) ────────────────────────
def _extract_title(html: str) -> str:
    """提取HTML <title> 标签内容。"""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _html_to_text(html: str) -> str:
    """将HTML转为纯文本(去除标签、脚本、样式)。"""
    # 移除 script/style 块
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<noscript[^>]*>.*?</noscript>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    # 移除 HTML 注释
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    # 块级标签转换行
    text = re.sub(r"<(?:br|hr|p|div|li|tr|h[1-6]|section|article)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # td/th加分隔符
    text = re.sub(r"<(?:td|th)[^>]*>", " | ", text, flags=re.IGNORECASE)
    # 移除其他标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 解码 HTML 实体
    text = _decode_html_entities(text)
    # 清理多余空白
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _decode_html_entities(text: str) -> str:
    """解码常见 HTML 实体。"""
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&apos;": "'",
        "&nbsp;": " ", "&mdash;": "—", "&ndash;": "–",
        "&hellip;": "…", "&copy;": "©", "&reg;": "®",
        "&yen;": "¥", "&dollar;": "$", "&euro;": "€",
        "&pound;": "£",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    # 数字实体: &#123; or &#x7B;
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    return text


def _extract_tables(html: str) -> List[Dict[str, Any]]:
    """提取HTML中所有<table>的内容为结构化数据。"""
    tables = []
    table_matches = re.finditer(r"<table[^>]*>(.*?)</table>", html, re.IGNORECASE | re.DOTALL)
    for i, table_match in enumerate(table_matches):
        table_html = table_match.group(1)
        rows = []
        for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, re.IGNORECASE | re.DOTALL):
            row_html = row_match.group(1)
            cells = []
            for cell_match in re.finditer(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", row_html, re.IGNORECASE | re.DOTALL):
                cell_text = re.sub(r"<[^>]+>", "", cell_match.group(1)).strip()
                cell_text = _decode_html_entities(cell_text)
                cells.append(cell_text)
            if cells:
                rows.append(cells)
        if rows:
            tables.append({"index": i, "rows": rows})
    return tables


def _json_to_text(data: Any, indent: int = 0) -> str:
    """将JSON数据转为可读文本。"""
    import json
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return str(data)
