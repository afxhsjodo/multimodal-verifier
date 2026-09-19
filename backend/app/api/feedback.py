"""人工复核 API：提交反馈、查看已有反馈与历史核验记录。"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.models import Feedback
from app.db import database

router = APIRouter()


@router.post("/feedback")
def submit_feedback(payload: Feedback):
    row = database.save_feedback(
        payload.task_id, payload.claim_id,
        payload.user_verdict.value if payload.user_verdict else "",
        payload.comment,
    )
    return {"ok": True, "feedback": row}


@router.get("/feedback")
def get_feedback(task_id: str | None = None):
    return {"ok": True, "feedback": database.list_feedback(task_id)}


@router.get("/history/{task_id}")
def get_history(task_id: str):
    data = database.get_verification(task_id)
    if data is None:
        return {"ok": False, "message": "not found"}
    return {"ok": True, "data": data}
