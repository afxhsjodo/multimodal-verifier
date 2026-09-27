"""证据重排序 Agent：在可信度评估之后，按分数对每条主张的证据排序并保留 top-K。

目的：把低可信 / 低相关证据挡在结论生成之外，降低噪声。
只影响「结论生成」所见的证据子集；`VerifyResult.evidences` 仍保留全部，
因此前端证据展示不受影响。
"""
from __future__ import annotations

import logging
import time

from app.agents.common import make_log
from app.core.models import Evidence, SourceAssessment

logger = logging.getLogger(__name__)

TOP_K = 6


def rerank(state: dict) -> dict:
    start = time.perf_counter()
    evidences: list[Evidence] = state.get("evidences", [])
    assessment: dict[str, SourceAssessment] = state.get("assessment", {})

    by_claim: dict[str, list[Evidence]] = {}
    for ev in evidences:
        by_claim.setdefault(ev.claim_id, []).append(ev)

    def score(ev: Evidence) -> float:
        a = assessment.get(ev.evidence_id)
        return a.total_score if a else 0.5

    selected: dict[str, list[str]] = {}
    for cid, evs in by_claim.items():
        ordered = sorted(evs, key=score, reverse=True)
        selected[cid] = [e.evidence_id for e in ordered[:TOP_K]]

    kept = sum(len(v) for v in selected.values())
    summary = f"重排序：{len(evidences)} 条证据 → 保留 {kept} 条（每主张 top-{TOP_K}）"
    return {"reranked": selected, "trace": [make_log("evidence_rerank", "证据重排序", start, summary)]}
