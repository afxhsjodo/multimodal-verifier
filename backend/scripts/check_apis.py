"""四类 API 连通性测试：DeepSeek chat/reasoner + DashScope embedding/vision。

用法：python scripts/check_apis.py
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import llm  # noqa: E402
from app.core.config import settings  # noqa: E402


def main() -> None:
    print(f"mock={llm.is_mock()} deepseek={settings.has_deepseek} dashscope={settings.has_dashscope}")

    # 1) DeepSeek 文本
    try:
        r = llm.chat([{"role": "user", "content": "用一句话介绍你自己"}], temperature=0)
        print("[chat] OK:", r[:50])
    except Exception as e:  # noqa: BLE001
        print("[chat] FAIL:", repr(e)[:200])

    # 2) DeepSeek 推理
    try:
        r = llm.reason([{"role": "user", "content": "1+1 等于几？只回答数字。"}])
        print("[reason] OK:", r[:50])
    except Exception as e:  # noqa: BLE001
        print("[reason] FAIL:", repr(e)[:200])

    # 3) DashScope embedding
    try:
        v = llm.embed(["测试向量"])
        print("[embed] OK dim:", len(v[0]), "前3:", [round(x, 4) for x in v[0][:3]])
    except Exception as e:  # noqa: BLE001
        print("[embed] FAIL:", repr(e)[:200])

    # 4) Qwen-VL 视觉（用一张极小的 PNG 测试链路是否通）
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    tmp = Path("data/tmp_vision.png")
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_bytes(png)
    try:
        r = llm.vision(str(tmp), "这张图里有什么？一句话回答。")
        print("[vision] OK:", r[:50])
    except Exception as e:  # noqa: BLE001
        print("[vision] FAIL:", repr(e)[:200])


if __name__ == "__main__":
    main()
