"""Agent 共用的轻量工具：步骤日志、耗时计时、ID 生成。"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from app.core.models import StepLog


def now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def make_log(agent: str, action: str, start: float, summary: str = "") -> StepLog:
    return StepLog(
        agent=agent,
        action=action,
        summary=summary,
        duration_ms=int((time.perf_counter() - start) * 1000),
        ts=now_iso(),
    )


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
