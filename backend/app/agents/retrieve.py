"""证据获取 Agent（并发版）：并行发起网页/文档检索，汇聚三类证据。

之前串行逐个查询调 Tavily，单次核验 30s+；改为并发后，总时长≈一次最慢调用。
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from app.agents.common import make_log, new_id
from app.core import llm
from app.core.models import Claim, Evidence, RetrievalTask
from app.tools import doc_retrieval, web_scrape, web_search

logger = logging.getLogger(__name__)

MAX_WEB_PER_CLAIM = 5
MAX_DOC_PER_CLAIM = 3
MAX_SCRAPE_PER_CLAIM = 3
MIN_CONTENT = 100  # 正文低于此长度才尝试抓取补充


def _vision_evidence(task: RetrievalTask, extracted_text: str) -> Evidence | None:
    text = extracted_text.strip()
    if not text:
        return None
    return Evidence(
        evidence_id=new_id("e"),
        claim_id=task.claim_id,
        text=text[:600],
        source_type="vision",
        title="输入图片内容",
        url="",
        source_name="用户上传图片",
        retrieval_method="视觉识别(Qwen-VL)",
    )


def _web_per_claim(tasks: list[RetrievalTask], is_mock: bool) -> dict[str, list[dict]]:
    """并发检索所有 (主张, 查询词) 组合，按主张归组并去重。"""
    if is_mock:
        return {}
    units = [(t, q) for t in tasks for q in t.queries if q]
    if not units:
        return {}

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(lambda u: (u, web_search.web_search(u[1], max_results=3)), units))

    per_claim: dict[str, list[dict]] = defaultdict(list)
    seen_urls: set[str] = set()
    for (task, _query), hits in results:
        for hit in hits:
            if len(per_claim[task.claim_id]) >= MAX_WEB_PER_CLAIM:
                break
            url = hit.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            per_claim[task.claim_id].append(
                {
                    "title": hit.get("title", ""),
                    "url": url,
                    "content": hit.get("content", "") or hit.get("snippet", ""),
                    "source_name": hit.get("source_name", ""),
                }
            )

    # 对正文过短的少量结果并发抓取补充正文
    for claim_id, items in per_claim.items():
        need = [it for it in items if len(it["content"]) < MIN_CONTENT][:MAX_SCRAPE_PER_CLAIM]
        if not need:
            continue
        with ThreadPoolExecutor(max_workers=len(need)) as ex:
            scraped = list(ex.map(lambda it: (it, web_scrape.fetch_page(it["url"])), need))
        for it, body in scraped:
            if body:
                it["content"] = body
    return per_claim


def _doc_per_claim(tasks: list[RetrievalTask]) -> dict[str, list[dict]]:
    units = [(t, q) for t in tasks for q in t.queries if q]
    if not units:
        return {}
    doc_retrieval._ensure_raw_chunks()  # 先单线程预载语料块，避免并发重复加载
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda u: (u, doc_retrieval.search_documents(u[1], top_k=MAX_DOC_PER_CLAIM)), units))

    per_claim: dict[str, list[dict]] = defaultdict(list)
    seen_ids: set[str] = set()
    for (task, _query), hits in results:
        for hit in hits:
            if len(per_claim[task.claim_id]) >= MAX_DOC_PER_CLAIM:
                break
            cid = hit.get("id", "")
            if cid in seen_ids or not hit.get("document"):
                continue
            seen_ids.add(cid)
            per_claim[task.claim_id].append(hit)
    return per_claim


def retrieve(state: dict) -> dict:
    start = time.perf_counter()
    is_mock = llm.is_mock()
    claims: dict[str, Claim] = {c.claim_id: c for c in state.get("claims", [])}
    tasks: list[RetrievalTask] = state.get("retrieval_plan", [])
    extracted_text = state.get("extracted_text", "")

    web_map = _web_per_claim(tasks, is_mock)
    doc_map = _doc_per_claim(tasks)

    evidences: list[Evidence] = []
    stats = {"web": 0, "document": 0, "vision": 0, "claims": len({t.claim_id for t in tasks})}

    for task in tasks:
        cid = task.claim_id
        if "vision" in task.sources or claims.get(cid, Claim(claim_id="", text="")).requires_vision:
            ev = _vision_evidence(task, extracted_text)
            if ev:
                evidences.append(ev)
                stats["vision"] += 1
        for w in web_map.get(cid, []):
            evidences.append(
                Evidence(
                    evidence_id=new_id("e"), claim_id=cid, text=w["content"][:800],
                    source_type="web", title=w["title"], url=w["url"],
                    source_name=w["source_name"], retrieval_method="网页检索(Tavily)",
                )
            )
            stats["web"] += 1
        for d in doc_map.get(cid, []):
            meta = d.get("metadata", {}) or {}
            evidences.append(
                Evidence(
                    evidence_id=new_id("e"), claim_id=cid, text=d["document"][:800],
                    source_type="document", title=meta.get("file", "本地语料"), url="",
                    source_name=meta.get("file", "本地语料"), retrieval_method="向量检索(Chroma)",
                )
            )
            stats["document"] += 1

    summary = (
        f"并发获取 {len(evidences)} 条证据（网页{stats['web']}/文档{stats['document']}/"
        f"图像{stats['vision']}），覆盖 {stats['claims']} 条主张，耗时"
    )
    return {"evidences": evidences, "trace": [make_log("evidence_retrieval", "获取证据", start, summary)]}
