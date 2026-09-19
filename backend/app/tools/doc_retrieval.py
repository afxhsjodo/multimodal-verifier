"""文档库检索：把本地语料（txt/md）分块、向量化入 Chroma，并支持语义检索。

embedding 依赖 DashScope；若不可用，doc_retrieval 退化为关键词重叠匹配，
保证 mock 模式下文档库也能给出部分证据。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from app.core import llm
from app.core.config import settings
from app.tools.vector_store import vector_store

logger = logging.getLogger(__name__)

# 模块级缓存，供关键词兜底匹配
_raw_chunks: list[dict] = []

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def _chunk(text: str, idx: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            # 尽量在句号/换行处断开
            cut = max(text.rfind("。", start, end), text.rfind(". ", start, end))
            if cut != -1:
                end = cut + 1
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP if end - CHUNK_OVERLAP > start else end
    return [f"[{idx}] {c}" for c in chunks]


def _collect_chunks() -> tuple[list[str], list[str], list[dict]]:
    """读取 corpus 目录下的 txt/md，分块。返回 (ids, docs, metadatas)。"""
    corpus_dir = settings.resolved_corpus_dir()
    files = sorted(list(corpus_dir.glob("*.txt")) + list(corpus_dir.glob("*.md"))) if corpus_dir.exists() else []
    ids: list[str] = []
    docs: list[str] = []
    metadatas: list[dict] = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for chunk in _chunk(text, 0):
            ids.append(f"{f.stem}-{len(ids)}")
            docs.append(chunk)
            metadatas.append({"file": f.name, "source": f.name})
    return ids, docs, metadatas


def _ensure_raw_chunks() -> None:
    """确保 _raw_chunks 已加载（懒加载，供关键词兜底匹配）。"""
    if not _raw_chunks:
        ids, docs, metadatas = _collect_chunks()
        _raw_chunks[:] = [
            {"id": ids[i], "document": docs[i], "metadata": metadatas[i]} for i in range(len(ids))
        ]


def build_index() -> dict:
    """读取 corpus_dir 下所有 txt/md，分块入向量库。返回统计信息。"""
    ids, docs, metadatas = _collect_chunks()
    _ensure_raw_chunks()  # 先填充原始块，保证 mock/未向量化也能关键词检索
    if not docs:
        return {"files": 0, "chunks": 0, "embedding": "none"}

    try:
        emb = llm.embed(docs)
    except llm.LLMUnavailable:
        logger.warning("embedding unavailable; index kept for keyword fallback")
        return {"files": len(set(m["file"] for m in metadatas)), "chunks": len(ids), "embedding": "keyword"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding failed: %s", exc)
        return {"files": len(set(m["file"] for m in metadatas)), "chunks": len(ids), "embedding": "keyword"}

    vector_store.add(ids, docs, emb, metadatas)
    return {"files": len(set(m["file"] for m in metadatas)), "chunks": len(ids), "embedding": "vector"}


def _terms(text: str) -> set[str]:
    """中文用字符 bigram + 短整词，英文用单词，便于模糊匹配。"""
    terms: set[str] = set()
    for run in re.findall(r"[一-龥]+", text):
        for i in range(len(run) - 1):
            terms.add(run[i : i + 2])
        if 2 <= len(run) <= 6:
            terms.add(run)
    for w in re.findall(r"[A-Za-z]{3,}", text):
        terms.add(w.lower())
    return terms


def _keyword_search(query: str, top_k: int) -> list[dict]:
    q_terms = _terms(query)
    if not q_terms:
        return []
    scored = []
    for chunk in _raw_chunks:
        doc = chunk["document"]
        overlap = sum(doc.count(t) for t in q_terms)
        if overlap:
            scored.append((overlap, chunk))
    scored.sort(key=lambda x: -x[0])
    out = []
    for overlap, chunk in scored[:top_k]:
        out.append(
            {
                "id": chunk["id"],
                "document": chunk["document"],
                "metadata": chunk["metadata"],
                "distance": 0.0,
                "_score": overlap,
            }
        )
    return out


def search_documents(query: str, top_k: int = 5) -> list[dict]:
    """语义检索（优先）或关键词兜底。返回统一结构的命中文档。"""
    _ensure_raw_chunks()
    try:
        emb = llm.embed([query])
    except llm.LLMUnavailable:
        return _keyword_search(query, top_k)
    except Exception as exc:  # noqa: BLE001
        logger.warning("search embedding failed: %s", exc)
        return _keyword_search(query, top_k)
    return vector_store.query(emb[0], top_k=top_k)
