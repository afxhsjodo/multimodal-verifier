"""可信度评估 Agent：对每条证据做来源可靠性打分与冲突检测。

采用「LLM 融合 + 规则兜底」策略：优先用 LLM 批量评估四维分数
（权威性/时效性/相关性/一致性），LLM 不可用或失败时回退规则打分，
保证离线可跑、结果可复现。
维度权重：权威性(0.4) + 相关性(0.3) + 时效性(0.15) + 一致性(0.15)。
"""
from __future__ import annotations

import logging
import re
import time

from app.agents.common import make_log
from app.core import llm, memory
from app.core.models import Claim, Evidence, SourceAssessment

logger = logging.getLogger(__name__)

WEIGHTS = {"authority": 0.4, "relevance": 0.3, "timeliness": 0.15, "consistency": 0.15}

# 权威来源白名单（域名或其子串命中即视为权威）
AUTHORITATIVE_MARKERS = [
    "gov.cn", "edu.cn", "who.int", "nature.com", "science.org", "nih.gov",
    "moe.gov.cn", "新华社", "人民网", "人民日报", "央视", "cctv", "sciencenet",
    "cas.cn", "ac.cn", "worldbank", "un.org", "bbc.com", "reuters.com",
]
# 低可信来源黑名单
LOW_TRUST_MARKERS = ["blogspot", "blog.com", "bestgossip", "daily-cn", "mystery-wu"]

NEG_WORDS = ["不是", "并没有", "并未", "不会", "禁止", "取消", "假的", "谣言", "并未发生"]
POS_WORDS = ["确实是", "已经", "正在", "确认", "属实", "发布", "开展", "举行"]

LLM_ASSESS_BATCH = 8

_LLM_ASSESS_SYSTEM = (
    "你是『可信度评估』Agent。对每条证据从四个维度打分，每个分数为 0~1 的小数：\n"
    "authority(来源权威性)、timeliness(时效性)、relevance(与主张相关性)、consistency(一致性)。\n"
    "只输出 JSON 数组，元素格式：\n"
    "{\"evidence_id\":str,\"authority\":float,\"timeliness\":float,\"relevance\":float,\"consistency\":float,\"note\":str}。"
)


def _clamp(x, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.5


def _authority(ev: Evidence) -> tuple[float, bool, str]:
    name = (ev.source_name or "").lower()
    url = (ev.url or "").lower()
    blob = f"{name} {url}"
    hit = next((m for m in LOW_TRUST_MARKERS if m in blob), None)
    if hit:
        return 0.2, False, f"命中低可信域名标记:{hit}"
    hit = next((m for m in AUTHORITATIVE_MARKERS if m in blob), None)
    if hit:
        return 0.95, True, f"命中权威来源标记:{hit}"
    if ev.source_type == "document":
        return 0.7, True, "来自本地语料库"
    if ev.source_type == "vision":
        return 0.6, False, "来自用户输入图片"
    return 0.55, False, "未知域名，来源一般"


def _lexical_overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[一-龥]{2,}|[A-Za-z]{3,}", a.lower()))
    tb = set(re.findall(r"[一-龥]{2,}|[A-Za-z]{3,}", b.lower()))
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta), 2)


def _relevance(claim_text: str, ev: Evidence) -> tuple[float, str]:
    score = _lexical_overlap(claim_text, ev.text)
    if score >= 0.5:
        return score, "与主张高度相关"
    if score >= 0.25:
        return score, "与主张部分相关"
    return score, "与主张相关性较弱"


def _timeliness(ev: Evidence) -> tuple[float, str]:
    if not ev.published_date:
        return 0.5, "发布时间未知"
    m = re.search(r"(20\d{2})", ev.published_date)
    if not m:
        return 0.5, "发布时间无法解析"
    year = int(m.group(1))
    score = max(0.1, min(1.0, (year - 2005) / 20))
    return round(score, 2), f"发布于{year}年"


def _llm_assess_batch(evidences: list[Evidence], claims: dict[str, Claim]) -> dict[str, dict]:
    """用 LLM 批量评估证据四维分数。返回 {evidence_id: {authority,...}}；失败/不可用返回空。"""
    if llm.is_mock():
        return {}
    out: dict[str, dict] = {}
    for i in range(0, len(evidences), LLM_ASSESS_BATCH):
        batch = evidences[i : i + LLM_ASSESS_BATCH]
        lines = []
        for ev in batch:
            claim = claims.get(ev.claim_id, Claim(claim_id="", text=""))
            lines.append(
                f"evidence_id={ev.evidence_id} | 主张={claim.text[:40]} | "
                f"来源={ev.source_name}({ev.url[:50]}) | 文本={ev.text[:120]}"
            )
        try:
            data = llm.chat_json(
                [{"role": "system", "content": _LLM_ASSESS_SYSTEM},
                 {"role": "user", "content": "\n".join(lines)}],
                hint="assess",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 评估失败（第 %d 批），回退规则: %s", i // LLM_ASSESS_BATCH, exc)
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            eid = str(item.get("evidence_id", ""))
            if not eid:
                continue
            out[eid] = {
                "authority": _clamp(item.get("authority")),
                "timeliness": _clamp(item.get("timeliness")),
                "relevance": _clamp(item.get("relevance")),
                "consistency": _clamp(item.get("consistency")),
                "note": str(item.get("note", "LLM 融合评估")),
            }
    return out


def _flag_conflicts(evidences: list[Evidence], assessments: dict[str, SourceAssessment]) -> None:
    """按 claim 分组，若存在明显的正/反两派信号则彼此标记冲突。"""
    by_claim: dict[str, list[str]] = {}
    for ev in evidences:
        by_claim.setdefault(ev.claim_id, []).append(ev.text)
    for claim_id, texts in by_claim.items():
        neg = sum(any(w in t for w in NEG_WORDS) for t in texts)
        pos = sum(any(w in t for w in POS_WORDS) for t in texts)
        conflict = neg >= 1 and pos >= 1
        if not conflict:
            continue
        for ev in evidences:
            if ev.claim_id != claim_id:
                continue
            a = assessments.get(ev.evidence_id)
            if not a:
                continue
            a.is_conflicting = True
            a.conflict_note = "同一主张下证据之间出现正反冲突，需谨慎"
            a.consistency_score = min(0.3, a.consistency_score)
            a.total_score = round(
                a.authority_score * WEIGHTS["authority"]
                + a.relevance_score * WEIGHTS["relevance"]
                + a.timeliness_score * WEIGHTS["timeliness"]
                + a.consistency_score * WEIGHTS["consistency"],
                2,
            )


def assess(state: dict) -> dict:
    start = time.perf_counter()
    claims: dict[str, Claim] = {c.claim_id: c for c in state.get("claims", [])}
    evidences: list[Evidence] = state.get("evidences", [])
    assessments: dict[str, SourceAssessment] = {}

    llm_scores = _llm_assess_batch(evidences, claims)
    llm_hits = 0

    for ev in evidences:
        claim = claims.get(ev.claim_id, Claim(claim_id="", text=""))
        s = llm_scores.get(ev.evidence_id)
        if s is not None:
            # LLM 融合评估
            auth, rel, time_s, cons = s["authority"], s["relevance"], s["timeliness"], s["consistency"]
            is_auth = auth >= 0.75
            note = s.get("note", "LLM 融合评估")
            llm_hits += 1
        else:
            # 规则兜底
            auth, is_auth, auth_note = _authority(ev)
            rel, rel_note = _relevance(claim.text, ev)
            time_s, time_note = _timeliness(ev)
            cons = round(0.5 + 0.3 * auth, 2)
            note = f"{auth_note}；{rel_note}；{time_note}"

        # 长期记忆反哺：来源被人工复核否定过则额外降权
        distrust = memory.get_distrust(ev.source_name)
        if distrust:
            auth = round(max(0.1, auth * (0.6 ** distrust)), 2)
            is_auth = False
            note = f"{note}；历史被人工复核否定 {distrust} 次，权威性降权"

        total = round(
            auth * WEIGHTS["authority"]
            + rel * WEIGHTS["relevance"]
            + time_s * WEIGHTS["timeliness"]
            + cons * WEIGHTS["consistency"],
            2,
        )
        assessments[ev.evidence_id] = SourceAssessment(
            evidence_id=ev.evidence_id,
            authority_score=auth,
            relevance_score=rel,
            timeliness_score=time_s,
            consistency_score=cons,
            total_score=total,
            is_authoritative=is_auth,
            note=note,
        )

    _flag_conflicts(evidences, assessments)

    strong = sum(1 for a in assessments.values() if a.total_score >= 0.6)
    conflict = sum(1 for a in assessments.values() if a.is_conflicting)
    mode = "LLM融合" if llm_hits else "规则"
    summary = f"评估 {len(assessments)} 条证据（{mode}{llm_hits}条），高可信 {strong} 条，冲突 {conflict} 条"
    return {"assessment": assessments, "trace": [make_log("credibility_assess", "可信度评估", start, summary)]}
