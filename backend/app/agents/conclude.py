"""结论生成 Agent：综合证据与可信度评估，为每条主张输出三类结论。

live 模式用 deepseek-reasoner 做推理；mock/失败时用确定性启发式判定。
任何「证据不足」或低置信度结论都强制标记人工复核。
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from app.agents.common import make_log
from app.core import llm
from app.core.models import (
    Claim,
    Evidence,
    SourceAssessment,
    Verdict,
    VerdictLabel,
)

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是『结论生成』Agent。根据给定的主张与检索到的证据，判定该主张属于\n"
    "support(支持)/refute(反驳)/insufficient(证据不足) 三者之一。\n"
    "硬性要求：\n"
    "1. 结论必须且只能从证据推断，禁止凭空猜测；\n"
    "2. evidence_refs 只能引用给定证据中的 id；\n"
    "3. 若证据不足或证据相互矛盾无法定论，一律判 insufficient；\n"
    "4. 只输出 JSON，格式：{\"verdict\":str,\"confidence\":float,\"evidence_refs\":str[],\"reasoning\":str}。"
)


def _fallback_verdict(claim: Claim, evs: list[Evidence], assessments: dict[str, SourceAssessment]) -> Verdict:
    if not evs:
        return Verdict(
            claim_id=claim.claim_id, claim_text=claim.text,
            verdict=VerdictLabel.INSUFFICIENT, confidence=0.1,
            evidence_refs=[], reasoning="未检索到任何相关证据，无法判断。",
            needs_review=True,
        )
    pos = 0
    neg = 0
    total_w = 0.0
    refs = []
    for ev in evs:
        a = assessments.get(ev.evidence_id)
        w = a.total_score if a else 0.5
        total_w += w
        if w < 0.25:
            continue
        refs.append(ev.evidence_id)
        if any(k in ev.text for k in ("不是", "并没有", "并未", "不会", "禁止", "取消", "假的", "谣言", "并非")):
            neg += 1
        if any(k in ev.text for k in ("确实是", "已经", "正在", "确认", "属实", "发布", "开展", "举行")):
            pos += 1

    avg_w = total_w / len(evs)
    if neg > pos and neg >= 1:
        verdict, confidence = VerdictLabel.REFUTE, round(min(0.95, 0.4 + avg_w * 0.5), 2)
        reasoning = "存在较强反驳证据，主张倾向被否定。"
    elif pos > neg and pos >= 1:
        verdict, confidence = VerdictLabel.SUPPORT, round(min(0.95, 0.4 + avg_w * 0.5), 2)
        reasoning = "存在较强支持证据，主张倾向成立。"
    else:
        verdict, confidence = VerdictLabel.INSUFFICIENT, round(0.3 + avg_w * 0.2, 2)
        reasoning = "证据不足以支持明确结论，建议人工复核。"

    return Verdict(
        claim_id=claim.claim_id, claim_text=claim.text,
        verdict=verdict, confidence=confidence, evidence_refs=refs,
        reasoning=reasoning, needs_review=(verdict == VerdictLabel.INSUFFICIENT),
    )


def _llm_verdict(claim: Claim, evs: list[Evidence], assessments: dict[str, SourceAssessment]) -> Verdict:
    ev_lines = []
    for ev in evs:
        a = assessments.get(ev.evidence_id)
        score = f"{a.total_score:.2f}" if a else "未知"
        ev_lines.append(f"- id={ev.evidence_id} 来源={ev.source_name} 可信度={score}\n  {ev.text[:200]}")
    user = (
        f"主张({claim.claim_id}): {claim.text}\n\n"
        f"检索到的证据：\n{chr(10).join(ev_lines) if ev_lines else '（无）'}\n\n"
        "请给出判定。"
    )
    data = llm.chat_json(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        hint="verdict",
    )
    valid_ids = {ev.evidence_id for ev in evs}
    raw_v = str(data.get("verdict", "insufficient")).lower()
    mapping = {"support": VerdictLabel.SUPPORT, "refute": VerdictLabel.REFUTE, "insufficient": VerdictLabel.INSUFFICIENT}
    verdict = mapping.get(raw_v, VerdictLabel.INSUFFICIENT)
    refs = [eid for eid in data.get("evidence_refs", []) if eid in valid_ids]
    confidence = max(0.0, min(1.0, float(data.get("confidence", 0.3))))
    return Verdict(
        claim_id=claim.claim_id, claim_text=claim.text,
        verdict=verdict, confidence=round(confidence, 2),
        evidence_refs=refs,
        reasoning=str(data.get("reasoning", "")),
        needs_review=(verdict == VerdictLabel.INSUFFICIENT),
    )


def conclude(state: dict) -> dict:
    start = time.perf_counter()
    claims: list[Claim] = state.get("claims", [])
    evidences: list[Evidence] = state.get("evidences", [])
    assessments: dict[str, SourceAssessment] = state.get("assessment", {})

    by_claim: dict[str, list[Evidence]] = {}
    for ev in evidences:
        by_claim.setdefault(ev.claim_id, []).append(ev)

    def _one(claim: Claim) -> Verdict:
        evs = by_claim.get(claim.claim_id, [])
        if evs and not llm.is_mock():
            try:
                return _llm_verdict(claim, evs, assessments)
            except Exception as exc:  # noqa: BLE001
                logger.warning("conclude LLM failed for %s, fallback: %s", claim.claim_id, exc)
        return _fallback_verdict(claim, evs, assessments)

    if len(claims) > 1 and not llm.is_mock():
        # 多条主张各自独立，并发推理以提速
        with ThreadPoolExecutor(max_workers=2) as ex:
            verdicts = list(ex.map(_one, claims))
    else:
        verdicts = [_one(c) for c in claims]

    support = sum(1 for v in verdicts if v.verdict == VerdictLabel.SUPPORT)
    refute = sum(1 for v in verdicts if v.verdict == VerdictLabel.REFUTE)
    insuf = sum(1 for v in verdicts if v.verdict == VerdictLabel.INSUFFICIENT)
    review = sum(1 for v in verdicts if v.needs_review)
    summary = f"结论：支持{support}/反驳{refute}/不足{insuf}，需复核{review}"
    return {"verdicts": verdicts, "trace": [make_log("conclusion", "生成结论", start, summary)]}
