"""主张拆解 Agent：把输入（文本+图片转写）拆成可独立核验的原子主张。"""
from __future__ import annotations

import logging
import re
import time

from app.agents.common import make_log, new_id
from app.core import llm
from app.core.models import Claim
from app.tools.ocr_vision import describe_image

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是『主张拆解』Agent。任务：把用户提供的内容拆解成若干条可独立核验的原子主张(claim)。\n"
    "要求：\n"
    "1. 一条信息可能包含多个独立观点，请逐个拆开；\n"
    "2. 只输出 JSON 数组，不要任何多余文字；\n"
    "3. 数组每个元素格式：{\"text\":str,\"claim_type\":str,\"topic\":str,\"requires_vision\":bool,\"source_ref\":str}；\n"
    "4. claim_type 取 fact(可验证事实) / opinion(观点) / event(事件)；\n"
    "5. topic 为该主张的简短主题关键词；requires_vision 表示是否依赖原图内容。"
)


def _fallback_claims(text: str) -> list[Claim]:
    """mock 或 LLM 失败时的确定性降级：按句子切分。"""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[。！？!?\n])", text)
    claims: list[Claim] = []
    seen: set[str] = set()
    for s in sentences:
        s = s.strip().strip("，,。. ")
        if len(s) < 5 or s in seen:
            continue
        seen.add(s)
        ctype = "fact"
        if any(k in s for k in ("最好", "最差", "应该", "认为", "高效", "优秀")):
            ctype = "opinion"
        elif re.search(r"\d{4}年|月|日|通知|发布|宣布", s):
            ctype = "event"
        claims.append(
            Claim(claim_id=new_id("c"), text=s, claim_type=ctype, topic=s[:12])
        )
        if len(claims) >= 6:
            break
    return claims


def _llm_claims(text: str) -> list[Claim]:
    data = llm.chat_json(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
        hint="claim",
    )
    if not isinstance(data, list):
        raise ValueError("claim 拆解返回非数组")
    claims: list[Claim] = []
    for item in data[:8]:
        claims.append(
            Claim(
                claim_id=new_id("c"),
                text=str(item.get("text", "")).strip(),
                claim_type=str(item.get("claim_type", "fact")),
                topic=str(item.get("topic", "")),
                requires_vision=bool(item.get("requires_vision", False)),
                source_ref=str(item.get("source_ref", "")),
            )
        )
    return [c for c in claims if c.text]


def decompose(state: dict) -> dict:
    start = time.perf_counter()
    # 1) 图片转写
    descriptions = []
    for img in state.get("image_paths", []) or []:
        desc = describe_image(img)
        if desc:
            descriptions.append(f"[图片内容] {desc}")

    parts = [state.get("source_text", "").strip()] + descriptions
    extracted_text = "\n".join(p for p in parts if p)

    # 2) 拆解主张
    claims: list[Claim] = []
    note = ""
    if extracted_text:
        if llm.is_mock():
            claims = _fallback_claims(extracted_text)
            note = "mock 模式，按句子切分"
        else:
            try:
                claims = _llm_claims(extracted_text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("decompose LLM failed, fallback: %s", exc)
                claims = _fallback_claims(extracted_text)
                note = f"LLM 失败，降级切分 ({exc})"

    summary = f"拆解出 {len(claims)} 条主张；{note}".strip("；")
    if descriptions:
        summary += f"；已识别 {len(descriptions)} 张图片"

    return {
        "extracted_text": extracted_text,
        "claims": claims,
        "trace": [make_log("claim_decompose", "拆解主张", start, summary)],
    }
