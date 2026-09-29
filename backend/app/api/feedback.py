"""人工复核 API：提交反馈、查看已有反馈与历史核验记录。

human-in-the-loop 闭环：提交复核时，若用户判定与系统结论不一致，将该主张的
证据来源记入长期记忆（source_trust），后续核验会对此来源自动降权。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.core import memory
from app.core.models import Feedback
from app.db import database

logger = logging.getLogger(__name__)
router = APIRouter()


def _apply_source_trust(payload: Feedback) -> int:
    """若用户判定与系统结论不同，把该主张的证据来源记入长期记忆，返回降权来源数。"""
    if not payload.user_verdict:
        return 0
    hist = database.get_verification(payload.task_id)
    if not hist:
        return 0
    sys_verdict = None
    for v in hist.get("verdicts", []):
        if v.get("claim_id") == payload.claim_id:
            sys_verdict = v.get("verdict")
            break
    user_v = payload.user_verdict.value
    if not sys_verdict or sys_verdict == user_v:
        return 0
    sources = set()
    for e in hist.get("evidences", []):
        if e.get("claim_id") == payload.claim_id:
            sn = (e.get("source_name") or "").strip()
            if sn:
                sources.add(sn)
    for sn in sources:
        memory.distrust_source(sn)
    if sources:
        logger.info("人工复核反哺：%s 被否定，降权来源 %s", payload.claim_id, sources)
    return len(sources)


@router.post("/feedback")
def submit_feedback(payload: Feedback):
    row = database.save_feedback(
        payload.task_id, payload.claim_id,
        payload.user_verdict.value if payload.user_verdict else "",
        payload.comment,
    )
    distrust_n = _apply_source_trust(payload)
    return {"ok": True, "feedback": row, "distrusted_sources": distrust_n}


@router.get("/feedback")
def get_feedback(task_id: str | None = None):
    return {"ok": True, "feedback": database.list_feedback(task_id)}


@router.get("/history/{task_id}")
def get_history(task_id: str):
    data = database.get_verification(task_id)
    if data is None:
        return {"ok": False, "message": "not found"}
    return {"ok": True, "data": data}
