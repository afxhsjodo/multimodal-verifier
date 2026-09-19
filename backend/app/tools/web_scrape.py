"""网页正文提取：trafilatura 优先，失败回退 BeautifulSoup。"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def fetch_page(url: str, max_chars: int = 8000) -> str:
    """抓取并提取网页正文纯文本，失败返回空串。"""
    try:
        resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_page %s failed: %s", url, exc)
        return ""

    text = _extract_text(html)
    return text[:max_chars]


def _extract_text(html: str) -> str:
    try:
        import trafilatura

        extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
        if extracted:
            return extracted.strip()
    except Exception as exc:  # noqa: BLE001
        logger.debug("trafilatura failed: %s", exc)

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
    except Exception as exc:  # noqa: BLE001
        logger.debug("beautifulsoup fallback failed: %s", exc)
        return ""
