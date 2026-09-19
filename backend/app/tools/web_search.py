"""网页检索：Tavily 优先，DuckDuckGo 兜底，统一返回 {title,url,snippet,content}。"""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 熔断：搜索失败后短时间内不再重试，避免在不可用的网络上反复等待
_last_fail: float = 0.0
_FAIL_COOLDOWN = 10  # 秒


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


def _to_result(raw: dict) -> dict[str, Any]:
    return {
        "title": raw.get("title", ""),
        "url": raw.get("url", raw.get("href", "")),
        "snippet": raw.get("snippet", raw.get("body", raw.get("content", ""))),
        "content": raw.get("content", raw.get("body", "")),
        "source_name": _domain(raw.get("url", raw.get("href", ""))),
    }


def _search_tavily(query: str, max_results: int) -> list[dict[str, Any]]:
    resp = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw_results = resp.json().get("results", [])
    return [_to_result(r) for r in raw_results]


def _search_duckduckgo(query: str, max_results: int) -> list[dict[str, Any]]:
    from duckduckgo_search import DDGS  # 延迟导入

    results: list[dict[str, Any]] = []
    with DDGS() as d:
        for hit in d.text(query, max_results=max_results):
            results.append(
                {
                    "title": hit.get("title", ""),
                    "url": hit.get("href", ""),
                    "snippet": hit.get("body", ""),
                    "content": hit.get("body", ""),
                    "source_name": _domain(hit.get("href", "")),
                }
            )
    return results


def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """执行一次网页检索，返回统一结构的结果列表（可能为空）。"""
    global _last_fail
    now = time.time()
    if _last_fail and now - _last_fail < _FAIL_COOLDOWN:
        return []  # 熔断期内，跳过不可用的网页搜索

    provider = settings.web_search_provider or "tavily"
    attempts: list[str] = []
    if provider in ("tavily", "both") and settings.tavily_api_key:
        attempts.append("tavily")
    if provider in ("duckduckgo", "both", "tavily") or not attempts:
        attempts.append("duckduckgo")

    last_err: Exception | None = None
    for prov in attempts:
        try:
            if prov == "tavily":
                return _search_tavily(query, max_results)
            return _search_duckduckgo(query, max_results)
        except Exception as exc:  # noqa: BLE001
            logger.warning("web_search provider %s failed: %s", prov, exc)
            last_err = exc
    if last_err:
        _last_fail = now  # 触发熔断，避免后续查询继续在失败网络上耗时
        logger.warning("web_search unavailable, cooling down %ss", _FAIL_COOLDOWN)
    return []
