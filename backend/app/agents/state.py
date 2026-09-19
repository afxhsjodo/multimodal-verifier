"""LangGraph 共享状态：贯穿 5 个 Agent 的可变数据总线。

列表字段用 add reducer 累加，便于多节点并行时合并结果。
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from app.core.models import (
    Claim,
    Evidence,
    RetrievalTask,
    SourceAssessment,
    StepLog,
    Verdict,
)


def _merge_list(left: list, right: list) -> list:
    return (left or []) + (right or [])


class VerdictState(TypedDict):
    # 输入
    source_text: str                     # 原始文本
    image_paths: list[str]               # 输入图片(截图)路径
    # 中间产物
    extracted_text: str                  # 图片转写 + 原始文本
    claims: Annotated[list[Claim], _merge_list]
    retrieval_plan: Annotated[list[RetrievalTask], _merge_list]
    evidences: Annotated[list[Evidence], _merge_list]
    assessment: dict[str, SourceAssessment]  # evidence_id -> 评估
    verdicts: Annotated[list[Verdict], _merge_list]
    trace: Annotated[list[StepLog], _merge_list]
    # 运行信息
    task_id: str
    mock: bool
