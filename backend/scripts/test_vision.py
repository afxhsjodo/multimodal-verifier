"""视觉链路测试：生成一张带中英文的真实图片，调用 Qwen-VL 转录，验证 OCR 能力。

用法：python scripts/test_vision.py
（依赖 Pillow；用 Windows 微软雅黑渲染中文。）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import llm  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

OUT = Path("data/test_img.png")


def make_image() -> str:
    img = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 44)
    draw.text((30, 30), "校园一卡通 2026年9月10日 正式上线", font=font, fill="black")
    draw.text((30, 120), "STOP  请勿传播不实信息", font=font, fill="red")
    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT)
    return str(OUT)


def main() -> None:
    path = make_image()
    print("已生成测试图:", path)
    try:
        r = llm.vision(path, "请完整转录图片中的所有文字，并简述图片主题。")
        print("[vision] Qwen-VL 返回:\n", r)
    except Exception as e:  # noqa: BLE001
        print("[vision] FAIL:", repr(e)[:300])


if __name__ == "__main__":
    main()
