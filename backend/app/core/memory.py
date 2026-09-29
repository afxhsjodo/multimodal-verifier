"""长期记忆：跨会话累积来源可信度（人工复核反哺评估）。

用 LangGraph 的 InMemoryStore 作运行时记忆，SQLite 持久化（启动加载、写入落盘），
体现「human-in-the-loop 闭环 + 长期记忆」：用户人工复核否定某来源后，该来源
在后续核验中会被自动降权。

当前记忆类型：source_trust（来源可信度，记录被人工复核否定的来源及次数）。
"""
from __future__ import annotations

import logging

from langgraph.store.memory import InMemoryStore

logger = logging.getLogger(__name__)

store = InMemoryStore()
_NAMESPACE = ("source_trust",)


def distrust_source(name: str) -> int:
    """记录一次来源被人工复核否定，返回累计否定次数。"""
    name = (name or "").strip()
    if not name:
        return 0
    cur = store.get(_NAMESPACE, name)
    count = (cur.value.get("distrust", 0) + 1) if cur else 1
    store.put(_NAMESPACE, name, {"distrust": count})
    try:
        from app.db import database

        database.save_source_trust(name, count)
    except Exception as exc:  # noqa: BLE001
        logger.warning("source_trust 持久化失败: %s", exc)
    return count


def get_distrust(name: str) -> int:
    name = (name or "").strip()
    if not name:
        return 0
    cur = store.get(_NAMESPACE, name)
    return cur.value.get("distrust", 0) if cur else 0


def load_all() -> int:
    """启动时从 SQLite 加载到内存 store，返回加载条数。"""
    try:
        from app.db import database

        rows = database.list_source_trust()
    except Exception as exc:  # noqa: BLE001
        logger.warning("加载 source_trust 失败: %s", exc)
        return 0
    for row in rows:
        store.put(_NAMESPACE, row["source"], {"distrust": row["distrust"]})
    return len(rows)
