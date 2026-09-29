"""端到端冒烟测试：mock 模式下跑通 5 个 Agent，验证输出结构完整。

用法：python scripts/smoke_test.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.graph import config_for, graph, new_initial_state  # noqa: E402
from app.core import llm  # noqa: E402

# 一句话测试样例（含可拆分主张 + 关键词命中文档库）
SAMPLE = (
    "网传我校新版校园一卡通将于2026年9月10日正式上线，且原有实体卡将立即停用，"
    "此事属谣言。另有说法称戴口罩完全无法预防流感，这两种说法都值得核实。"
)


def main() -> None:
    print(f"mock 模式: {llm.is_mock()}")
    initial = new_initial_state("smoke-001", SAMPLE, [], llm.is_mock())
    state = graph.invoke(initial, config=config_for("smoke-001"))

    print("\n=== 主张 ===")
    for c in state["claims"]:
        print(f"  [{c.claim_id}] {c.claim_type}: {c.text}")

    print("\n=== 证据 ===")
    for e in state["evidences"]:
        print(f"  [{e.evidence_id}] {e.source_type} {e.source_name}: {e.text[:50]}...")

    print("\n=== 结论 ===")
    for v in state["verdicts"]:
        print(f"  {v.claim_text[:30]} => {v.verdict} (conf={v.confidence}, review={v.needs_review})")

    print("\n=== 轨迹 ===")
    for s in state["trace"]:
        print(f"  {s.agent}: {s.action} ({s.duration_ms}ms) - {s.summary}")

    # 校验核心字段
    assert state["claims"], "无主张"
    assert state["verdicts"], "无结论"
    for v in state["verdicts"]:
        assert v.disclaimer, "缺失免责声明"
        if v.verdict == "insufficient":
            assert v.needs_review, "证据不足的主张某未标记需人工复核"
    print("\n✅ 冒烟测试通过：结构完整，免责声明与人工复核标记齐全")


if __name__ == "__main__":
    main()
