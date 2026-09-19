"""后端 API 冒烟测试：health + POST /verify + WS 流式。用 TestClient，无需启动服务。

用法：python tests/test_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

TEXT = "网传我校新版校园一卡通将于2026年9月10日上线，原有实体卡立即停用，此属谣言。"


def main() -> None:
    client = TestClient(app)

    # 1) health
    h = client.get("/health").json()
    print("health:", h)
    assert h["status"] == "ok"

    # 2) POST /verify（multipart 文本）
    r = client.post("/verify", data={"text": TEXT})
    print("POST /verify status:", r.status_code)
    body = r.json()
    assert r.status_code == 200
    assert body["verdicts"], "verdicts 为空"
    assert body["mode"] in ("live", "mock")
    # 结论类型是字符串
    for v in body["verdicts"]:
        assert v["verdict"] in ("support", "refute", "insufficient")
        assert v["disclaimer"], "缺免责声明"
    print(f"  claims={len(body['claims'])} evidences={len(body['evidences'])} verdicts={len(body['verdicts'])}")
    task_id = body["task_id"]

    # 3) WS 流式
    steps = []
    result = None
    with client.websocket_connect("/ws/verify") as ws:
        ws.send_json({"text": TEXT, "images": []})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "step":
                steps.append(msg)
            elif msg["type"] == "result":
                result = msg
            if msg["type"] == "result" or msg["type"] == "error":
                break
    assert result is not None, "WS 未返回 result"
    assert steps, "WS 未返回任何步骤"
    print(f"  WS steps={len(steps)} 覆盖节点={sorted({s['agent'] for s in steps})}")

    # 4) 人工复核
    fb = client.post("/feedback", json={"task_id": task_id, "claim_id": "any", "user_verdict": "insufficient", "comment": "测试"})
    print("POST /feedback:", fb.status_code, fb.json())

    print("\n✅ 后端 API 冒烟测试通过")


if __name__ == "__main__":
    main()
