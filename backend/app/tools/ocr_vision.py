"""图像理解：封装 Qwen-VL，将图片转为文字描述/OCR 结果。"""
from __future__ import annotations

import logging

from app.core import llm

logger = logging.getLogger(__name__)

_VISION_DESCRIBE_PROMPT = (
    "请仔细描述这张图片的内容。如果图片中包含文字、通知、截图、数字或表格，"
    "请完整、忠实地转录其中的文字内容，并说明图片的来源背景。"
    "请用中文回答，只输出描述与文字转录，不要额外评论。"
)


def describe_image(image_path: str, prompt: str = _VISION_DESCRIBE_PROMPT) -> str:
    """用 Qwen-VL 理解图片，返回文字描述/OCR 结果。失败返回空串。"""
    try:
        return llm.vision(image_path, prompt).strip()
    except llm.LLMUnavailable:
        logger.warning("vision unavailable (no dashscope key); skip image")
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("describe_image failed: %s", exc)
        return ""
