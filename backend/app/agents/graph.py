"""LangGraph 编排：把 5 个 Agent 连成有状态工作流。

记忆机制：用 SQLite checkpointer 持久化每次核验的完整状态（各 Agent 中间产物
与执行轨迹）。调用时以 task_id 作为 thread_id，即可在任意时刻恢复 / 回溯某次
核验的执行过程，实现 Agent 的「状态记忆」。
"""
from __future__ import annotations

import sqlite3
import threading

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from app.agents import assess, conclude, decompose, plan, rerank, retrieve
from app.agents.state import VerdictState
from app.core.config import settings


def _make_checkpointer() -> SqliteSaver:
    path = settings.project_root / "data" / "checkpoints.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(conn)


_checkpointer = _make_checkpointer()


def build_graph():
    g = StateGraph(VerdictState)
    g.add_node("claim_decompose", decompose.decompose)
    g.add_node("retrieval_plan", plan.plan)
    g.add_node("evidence_retrieval", retrieve.retrieve)
    g.add_node("credibility_assess", assess.assess)
    g.add_node("evidence_rerank", rerank.rerank)
    g.add_node("conclusion", conclude.conclude)
    g.set_entry_point("claim_decompose")
    g.add_edge("claim_decompose", "retrieval_plan")
    g.add_edge("retrieval_plan", "evidence_retrieval")
    g.add_edge("evidence_retrieval", "credibility_assess")
    g.add_edge("credibility_assess", "evidence_rerank")
    g.add_edge("evidence_rerank", "conclusion")
    g.add_edge("conclusion", END)
    return g.compile(checkpointer=_checkpointer)


def config_for(task_id: str) -> dict:
    """构造带 thread_id 的 config，使 LangGraph 按 task_id 持久化/恢复状态。"""
    return {"configurable": {"thread_id": task_id}}


def new_initial_state(task_id: str, source_text: str, image_paths: list[str], mock: bool) -> dict:
    """构造符合 VerdictState 的初始状态（所有键都显式初始化，便于 LangGraph 通道管理）。"""
    return {
        "source_text": source_text,
        "image_paths": image_paths,
        "extracted_text": "",
        "claims": [],
        "retrieval_plan": [],
        "evidences": [],
        "assessment": {},
        "reranked": {},
        "verdicts": [],
        "trace": [],
        "task_id": task_id,
        "mock": mock,
    }


graph = build_graph()
