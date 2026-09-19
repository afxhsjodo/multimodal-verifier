"""构建文档库索引：读取 corpus 目录，分块、向量化并写入 Chroma。

用法：python scripts/build_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.doc_retrieval import build_index  # noqa: E402
from app.core import llm  # noqa: E402


if __name__ == "__main__":
    print(f"mock 模式: {llm.is_mock()}")
    stats = build_index()
    print("索引统计:", stats)
