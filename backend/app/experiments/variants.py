"""实验变体：基线（纯 LLM）与单 Agent（一次 RAG），以及可跳过步骤的管道组合。

设计：各 Agent 均为「state dict 进、部分 dict 出」的纯函数，故可直接顺序组合，
无需为消融改 LangGraph 图。full 配置等价于线上 graph.invoke。
"""
from __future__ import annotations

import logging

from app.agents import assess, conclude, decompose, plan, rerank, retrieve
from app.agents.graph import new_initial_state
from app.core import llm
from app.core.models import VerdictLabel

logger = logging.getLogger(__name__)


def _apply(state: dict, update: dict) -> dict:
    """把 Agent 返回的部分 dict 合并进 state；trace 采用追加语义。"""
    for k, v in update.items():
        if k == "trace":
            state.setdefault("trace", []).extend(v)
        else:
            state[k] = v
    return state


def _aggregate(verdicts: list) -> str:
    """把一条样本（原子主张）的多个 claim 结论聚合为样本级预测：多数票，平票取不足。"""
    if not verdicts:
        return VerdictLabel.INSUFFICIENT.value
    counts: dict[str, int] = {}
    for v in verdicts:
        key = v.verdict.value if hasattr(v.verdict, "value") else str(v.verdict)
        counts[key] = counts.get(key, 0) + 1
    best = max(counts.values())
    top = [k for k, c in counts.items() if c == best]
    if len(top) == 1:
        return top[0]
    return VerdictLabel.INSUFFICIENT.value


# ---------- 完整管道 / 可跳过步骤 ----------
def run_pipeline(text: str, task_id: str = "exp", skip_assess: bool = False, skip_rerank: bool = False) -> dict:
    state = new_initial_state(task_id, text, [], llm.is_mock())
    _apply(state, decompose.decompose(state))
    _apply(state, plan.plan(state))
    _apply(state, retrieve.retrieve(state))
    if not skip_assess:
        _apply(state, assess.assess(state))
    if not skip_rerank:
        _apply(state, rerank.rerank(state))
    _apply(state, conclude.conclude(state))
    return state


# ---------- 基线：单 LLM，无检索、无 Agent ----------
_BASE_SYSTEM = (
    "你是事实核验助手。请**仅依据你自己的知识**（不要假设任何检索结果）判断给定主张属于\n"
    "support(支持)/refute(反驳)/insufficient(证据不足) 三者之一。\n"
    "只输出 JSON：{\"verdict\":str,\"confidence\":float,\"reasoning\":str}。"
)


def run_baseline(text: str) -> dict:
    data = llm.chat_json(
        [{"role": "system", "content": _BASE_SYSTEM}, {"role": "user", "content": f"主张：{text}"}],
        hint="baseline",
    )
    return _wrap_single(data)


# ---------- 单 Agent：一次 RAG（检索 + 一次判定），不拆解/规划/评估 ----------
_SINGLE_SYSTEM = (
    "你是事实核验助手。下面是针对某主张检索到的证据，请据其判定该主张属于\n"
    "support(支持)/refute(反驳)/insufficient(证据不足)。\n"
    "只输出 JSON：{\"verdict\":str,\"confidence\":float,\"reasoning\":str}。"
)


def _fetch_evidence_text(text: str, max_web: int = 5, max_doc: int = 3) -> list[str]:
    from app.tools import doc_retrieval, web_search

    snippets: list[str] = []
    for hit in web_search.web_search(text, max_results=max_web):
        content = hit.get("content") or hit.get("snippet") or ""
        if content:
            snippets.append(f"[网页] {hit.get('source_name','')}: {content[:300]}")
    for hit in doc_retrieval.search_documents(text, top_k=max_doc):
        doc = hit.get("document", "")
        if doc:
            snippets.append(f"[文档] {doc[:300]}")
    return snippets


def run_single_agent(text: str) -> dict:
    snippets = _fetch_evidence_text(text)
    ev_block = "\n".join(snippets) if snippets else "（未检索到证据）"
    data = llm.chat_json(
        [
            {"role": "system", "content": _SINGLE_SYSTEM},
            {"role": "user", "content": f"主张：{text}\n\n证据：\n{ev_block}"},
        ],
        hint="single_agent",
    )
    result = _wrap_single(data)
    result["n_evidence"] = len(snippets)
    return result


def _wrap_single(data: dict) -> dict:
    raw = str(data.get("verdict", "insufficient")).lower()
    mapping = {"support": "support", "refute": "refute", "insufficient": "insufficient"}
    verdict = mapping.get(raw, "insufficient")
    conf = data.get("confidence", 0.3)
    try:
        conf = max(0.0, min(1.0, float(conf)))
    except (TypeError, ValueError):
        conf = 0.3
    return {"verdict": verdict, "confidence": round(conf, 2), "reasoning": str(data.get("reasoning", ""))}
