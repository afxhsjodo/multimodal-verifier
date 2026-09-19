"""Chroma 向量库封装：显式传入 embedding，避免默认 onnx embedding 下载。"""
from __future__ import annotations

import logging
import threading
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self._client = None
        self._collection_name = settings.chroma_collection
        self._dir = settings.resolved_chroma_dir()
        self._lock = threading.Lock()

    def _init(self):
        if self._client is not None:
            return
        with self._lock:
            if self._client is not None:
                return
            import chromadb

            self._dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._dir))
            # embedding_function=None 表示使用我们显式传入的 embedding
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )

    @property
    def collection(self):
        self._init()
        return self._collection

    def count(self) -> int:
        self._init()
        return self._collection.count()

    def add(self, ids: list[str], documents: list[str], embeddings: list[list[float]], metadatas: list[dict[str, Any]] | None = None) -> None:
        self._init()
        n = len(documents)
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas or [{}] * n,
        )

    def query(self, embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """按向量召回，返回 [{id, document, metadata, distance}]。"""
        self._init()
        if self._collection.count() == 0:
            return []
        res = self._collection.query(query_embeddings=[embedding], n_results=top_k)
        out: list[dict[str, Any]] = []
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i, doc in enumerate(docs):
            out.append(
                {
                    "id": ids[i] if i < len(ids) else "",
                    "document": doc,
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": dists[i] if i < len(dists) else 1.0,
                }
            )
        return out


vector_store = VectorStore()
