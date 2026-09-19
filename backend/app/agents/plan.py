"""检索规划 Agent：为每条主张生成检索计划（查询词、目标源、证据类型）。"""
from __future__ import annotations

import logging
import time

from app.agents.common import make_log
from app.core import llm
from app.core.models import Claim, RetrievalTask

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是『检索规划』Agent。任务：针对每条主张，规划如何检索证据。\n"
    "只输出 JSON 数组，数组元素对应输入的每条主张，格式：\n"
    "{\"queries\":str[],\"sources\":str[],\"expected_evidence_type\":str}\n"
    "sources 从 web / document / vision 中选取；查询词应给出多个不同表述以提高召回。"
)


def _fallback_plan(claims: list[Claim]) -> list[RetrievalTask]:
    tasks = []
    for c in claims:
        queries = [c.text] if c.text else [c.topic]
        # 简单扩充：若主张含数字关键词则加一个简洁查询
        if c.topic and c.topic not in queries:
            queries.append(c.topic)
        sources = ["web", "document"]
        if c.requires_vision:
            sources.append("vision")
        tasks.append(
            RetrievalTask(
                claim_id=c.claim_id, queries=queries, sources=sources,
                expected_evidence_type=c.claim_type,
            )
        )
    return tasks


def _llm_plan(claims: list[Claim]) -> list[RetrievalTask]:
    claim_lines = "\n".join(f"- {c.claim_id}: {c.text}" for c in claims)
    data = llm.chat_json(
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"请为以下主张生成检索计划（保持数组顺序与主张一一对应）：\n{claim_lines}",
            },
        ],
        hint="plan",
    )
    if not isinstance(data, list):
        raise ValueError("plan 返回非数组")
    tasks: list[RetrievalTask] = []
    for i, item in enumerate(data):
        c = claims[i] if i < len(claims) else None
        if c is None:
            break
        sources = [s for s in item.get("sources", []) if s in ("web", "document", "vision")]
        tasks.append(
            RetrievalTask(
                claim_id=c.claim_id,
                queries=list(item.get("queries", [])) or [c.text],
                sources=sources or ["web"],
                expected_evidence_type=str(item.get("expected_evidence_type", c.claim_type)),
            )
        )
    return tasks


def plan(state: dict) -> dict:
    start = time.perf_counter()
    claims: list[Claim] = state.get("claims", [])
    tasks: list[RetrievalTask] = []
    note = ""
    if claims:
        if llm.is_mock():
            tasks = _fallback_plan(claims)
            note = "mock 模式"
        else:
            try:
                tasks = _llm_plan(claims)
            except Exception as exc:  # noqa: BLE001
                logger.warning("plan LLM failed, fallback: %s", exc)
                tasks = _fallback_plan(claims)
                note = f"LLM 失败，降级 ({exc})"
    if len(tasks) < len(claims):
        # 补齐缺失
        have = {t.claim_id for t in tasks}
        tasks += [t for t in _fallback_plan(claims) if t.claim_id not in have]

    summary = f"生成 {len(tasks)} 个检索计划；{note}".strip("；")
    return {"retrieval_plan": tasks, "trace": [make_log("retrieval_plan", "规划检索", start, summary)]}
