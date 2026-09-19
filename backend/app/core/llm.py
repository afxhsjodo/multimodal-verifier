"""统一 LLM 客户端：封装 DeepSeek 文本、Qwen-VL 视觉、DashScope embedding。

设计要点：
- DeepSeek 与 DashScope 均兼容 OpenAI 协议，故复用一个 OpenAI SDK 客户端。
- 当缺少对应 API key 时进入 mock / 离线模式：抛 LLMUnavailable，由上层 Agent 走
  确定性降级逻辑，保证无 key 也能跑通全流程与前端演示。
- chat_json 负责把 LLM 返回的 JSON（可能带 ``` 围栏/前后杂讯）稳健解析出来。
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.core.config import settings


class LLMUnavailable(Exception):
    """缺少相应 API key 时的占位异常，由上层 Agent 捕获并走降级逻辑。"""


_providers: dict[str, OpenAI] = {}


def _client(base_url: str, api_key: str) -> OpenAI:
    key = f"{base_url}|{api_key}"
    if key not in _providers:
        _providers[key] = OpenAI(base_url=base_url, api_key=api_key)
    return _providers[key]


def is_mock() -> bool:
    """整体是否处于 mock 模式（没有 DeepSeek key，文本走降级）。"""
    return not settings.has_deepseek


def _extract_json(text: str) -> Any:
    """从 LLM 文本中稳健抽取 JSON 对象或数组。"""
    text = text.strip()
    # 去掉 markdown 代码围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 定位第一个 { 或 [ 并截取
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("no JSON object/array found")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    end = text.rfind(closer)
    return json.loads(text[start : end + 1])


def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """调用 DeepSeek 文本模型，返回纯文本。无 key 时抛 LLMUnavailable。"""
    if not settings.has_deepseek:
        raise LLMUnavailable("deepseek api key missing")
    model = model or settings.deepseek_chat_model
    client = _client(settings.deepseek_base_url, settings.deepseek_api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def chat_json(messages: list[dict[str, str]], hint: str = "") -> Any:
    """调用 DeepSeek 并解析出 JSON。hint 仅用于日志/错误信息，不改变行为。"""
    content = chat(messages)
    try:
        return _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"LLM JSON 解析失败 (hint={hint}): {exc}") from exc


def reason(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    """调用 DeepSeek 推理模型（deepseek-reasoner），用于结论生成。"""
    return chat(messages, model=settings.deepseek_reasoner_model, temperature=temperature)


def vision(image_path: str, prompt: str) -> str:
    """Qwen-VL 视觉理解：识别图片内容 / 提取文字。无 key 时抛 LLMUnavailable。"""
    if not settings.has_dashscope:
        raise LLMUnavailable("dashscope api key missing")
    client = _client(settings.dashscope_base_url, settings.dashscope_api_key)
    image_url = _to_data_url(image_path)
    resp = client.chat.completions.create(
        model=settings.qwen_vl_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return resp.choices[0].message.content or ""


def _to_data_url(image_path: str) -> str:
    """把本地图片转成 base64 data url 传给视觉模型。"""
    import base64
    import mimetypes

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    mime = mimetypes.guess_type(image_path)[0] or "image/png"
    return f"data:{mime};base64,{b64}"


def embed(texts: list[str]) -> list[list[float]]:
    """DashScope text-embedding-v3 向量化。无 key 时抛 LLMUnavailable。"""
    if not settings.has_dashscope:
        raise LLMUnavailable("dashscope api key missing")
    client = _client(settings.dashscope_base_url, settings.dashscope_api_key)
    # DashScope embedding 走的是 /embeddings 端点
    resp = client.embeddings.create(model=settings.qwen_embed_model, input=texts)
    # 兼容返回结构：resp.data 为 {embedding, index, ...}
    return [item.embedding for item in resp.data]
