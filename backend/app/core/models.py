"""Pydantic 数据模型：贯穿 5 个 Agent 的中间产物与最终输出。"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

DISCLAIMER = (
    "本结果由 AI 自动生成，仅供参考，不构成权威结论。模型可能出错，"
    "且可能检索到不完整或相互矛盾的信息。对标注为『证据不足』或重要的事实，"
    "请务必通过人工复核并使用可靠的权威来源进行确认。"
)

# 结论三类
class VerdictLabel(str, Enum):
    SUPPORT = "support"            # 支持
    REFUTE = "refute"              # 反驳
    INSUFFICIENT = "insufficient"  # 证据不足

EVIDENCE_SOURCES = ["web", "document", "vision"]
CLAIM_TYPES = ["fact", "opinion", "event"]


class Claim(BaseModel):
    """主张拆解 Agent 产出的可独立核验的原子主张。"""
    claim_id: str
    text: str
    claim_type: str = "fact"        # fact / opinion / event
    topic: str = ""
    requires_vision: bool = False   # 是否依赖图片内容
    source_ref: str = ""            # 原始输入中的定位(可选)


class RetrievalTask(BaseModel):
    """检索规划 Agent 为某条主张生成的检索计划。"""
    claim_id: str
    queries: list[str] = []         # 多组查询词
    sources: list[str] = ["web"]    # 期望检索源: web/document/vision
    expected_evidence_type: str = "fact"


class Evidence(BaseModel):
    """证据获取 Agent 检索到的一条证据。"""
    evidence_id: str
    claim_id: str
    text: str
    source_type: str = "web"        # web / document / vision
    title: str = ""
    url: str = ""                   # 溯源链接(可空)
    source_name: str = ""           # 域名/文档名
    published_date: str = ""        # 发布时间(可空)
    retrieval_method: str = ""      # 检索方式(搜索/正文抓取/向量检索/视觉识别)


class SourceAssessment(BaseModel):
    """可信度评估 Agent 对单条证据的打分与冲突标注。"""
    evidence_id: str
    authority_score: float = 0.0    # 来源权威性 0-1
    timeliness_score: float = 0.0   # 时效性 0-1
    relevance_score: float = 0.0    # 相关性 0-1
    consistency_score: float = 0.0  # 一致性 0-1
    total_score: float = 0.0        # 加权总分 0-1
    is_authoritative: bool = False  # 是否权威来源
    is_conflicting: bool = False    # 与其他证据是否冲突
    conflict_note: str = ""         # 冲突说明
    note: str = ""


class Verdict(BaseModel):
    """结论生成 Agent 对单条主张的输出。"""
    claim_id: str
    claim_text: str
    verdict: VerdictLabel
    confidence: float = 0.0         # 置信度 0-1
    evidence_refs: list[str] = []   # 支撑该结论的证据 id
    reasoning: str = ""             # 推理说明
    needs_review: bool = False      # 是否需人工复核
    disclaimer: str = DISCLAIMER    # 免责声明
    reviewed: bool = False          # 是否已人工复核


class StepLog(BaseModel):
    """每个 Agent 节点的执行日志，用于前端实时展示与审计。"""
    agent: str
    action: str
    summary: str = ""
    duration_ms: int = 0
    ts: str = ""


class VerifyResult(BaseModel):
    """一次核验的完整输出。"""
    task_id: str
    source_text: str = ""           # 原始文本
    extracted_text: str = ""        # 图片转写 + 文本
    claims: list[Claim] = []
    evidences: list[Evidence] = []
    assessments: list[SourceAssessment] = []
    verdicts: list[Verdict] = []
    trace: list[StepLog] = []
    disclaimer: str = DISCLAIMER
    mode: str = "live"              # live / mock


class Feedback(BaseModel):
    """人工复核反馈。"""
    task_id: str
    claim_id: str
    user_verdict: Optional[VerdictLabel] = None
    comment: str = ""
