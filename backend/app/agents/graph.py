"""LangGraph 编排：把 5 个 Agent 连成有状态工作流。"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents import assess, conclude, decompose, plan, retrieve
from app.agents.state import VerdictState


def build_graph():
    g = StateGraph(VerdictState)
    g.add_node("claim_decompose", decompose.decompose)
    g.add_node("retrieval_plan", plan.plan)
    g.add_node("evidence_retrieval", retrieve.retrieve)
    g.add_node("credibility_assess", assess.assess)
    g.add_node("conclusion", conclude.conclude)
    g.set_entry_point("claim_decompose")
    g.add_edge("claim_decompose", "retrieval_plan")
    g.add_edge("retrieval_plan", "evidence_retrieval")
    g.add_edge("evidence_retrieval", "credibility_assess")
    g.add_edge("credibility_assess", "conclusion")
    g.add_edge("conclusion", END)
    return g.compile()


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
        "verdicts": [],
        "trace": [],
        "task_id": task_id,
        "mock": mock,
    }


graph = build_graph()
