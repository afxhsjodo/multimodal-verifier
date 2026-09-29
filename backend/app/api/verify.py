"""核验 API：POST /verify（同步全量） + WS /ws/verify（流式推送 Agent 步骤）。"""
from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect

from app.agents.graph import config_for, graph, new_initial_state
from app.core import llm
from app.core.models import VerifyResult
from app.db import database

logger = logging.getLogger(__name__)
router = APIRouter()

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def _to_result(state: dict) -> VerifyResult:
    return VerifyResult(
        task_id=state.get("task_id", ""),
        source_text=state.get("source_text", ""),
        extracted_text=state.get("extracted_text", ""),
        claims=state.get("claims", []),
        evidences=state.get("evidences", []),
        assessments=list(state.get("assessment", {}).values()),
        verdicts=state.get("verdicts", []),
        trace=state.get("trace", []),
        mode="mock" if state.get("mock") else "live",
    )


def _save_images(task_id: str, files: list[UploadFile]) -> list[str]:
    """把上传的图片落盘，返回文件路径列表。"""
    task_dir = _UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for i, f in enumerate(files):
        data = f.file.read()
        ext = Path(f.filename or f"img{i}").suffix or ".png"
        dest = task_dir / f"{i}{ext}"
        dest.write_bytes(data)
        paths.append(str(dest))
    return paths


def _save_images_payload(task_id: str, payload: list[dict]) -> list[str]:
    task_dir = _UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for i, item in enumerate(payload):
        name = item.get("name", f"img{i}")
        ext = Path(name).suffix or ".png"
        dest = task_dir / f"{i}{ext}"
        dest.write_bytes(base64.b64decode(item.get("data", "")))
        paths.append(str(dest))
    return paths


@router.post("/verify", response_model=VerifyResult)
def verify(
    text: str = Form(""),
    images: list[UploadFile] = File(default=[]),
):
    """同步核验：接收文本 + 图片，返回完整结论、证据与 Agent 执行轨迹。"""
    import time as _t

    task_id = f"{int(_t.time())}-{uuid.uuid4().hex[:6]}"
    image_paths = _save_images(task_id, images) if images else []
    initial = new_initial_state(task_id, text, image_paths, llm.is_mock())
    state = graph.invoke(initial, config=config_for(task_id))
    result = _to_result(state)
    database.save_verification(task_id, text, result.model_dump(), result.mode)
    return result


@router.websocket("/ws/verify")
async def ws_verify(ws: WebSocket):
    """WebSocket 流式：客户端发 {text, images:[{name,data(base64)}]}，逐节点推送更新。"""
    await ws.accept()
    try:
        payload = await ws.receive_json()
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "message": f"invalid payload: {exc}"})
        await ws.close()
        return

    task_id = str(payload.get("task_id") or f"ws-{uuid.uuid4().hex[:8]}")
    text = payload.get("text", "")
    image_paths = _save_images_payload(task_id, payload.get("images", [])) or []
    initial = new_initial_state(task_id, text, image_paths, llm.is_mock())

    # 用同步 stream（SqliteSaver 仅支持同步）在后台线程执行，经 asyncio 队列边跑边推
    final_state: dict | None = None
    sent: int = 0
    queue: asyncio.Queue = asyncio.Queue()

    def _run() -> None:
        try:
            for chunk in graph.stream(initial, config=config_for(task_id), stream_mode="values"):
                queue.put_nowait(chunk)
        except Exception as exc:  # noqa: BLE001
            queue.put_nowait({"__error__": str(exc)})
        finally:
            queue.put_nowait(None)

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run)

    try:
        while True:
            state_chunk = await queue.get()
            if state_chunk is None:
                break
            if "__error__" in state_chunk:
                raise RuntimeError(state_chunk["__error__"])
            final_state = state_chunk
            trace = state_chunk.get("trace", [])
            for step in trace[sent:]:
                sent += 1
                await ws.send_json(
                    {"type": "step", "node": step.agent, "agent": step.agent, "action": step.action,
                     "summary": step.summary, "duration_ms": step.duration_ms, "ts": step.ts}
                )
        result = _to_result(final_state or initial)
        database.save_verification(task_id, text, result.model_dump(), result.mode)
        await ws.send_json({"type": "result", "task_id": task_id, "data": result.model_dump(mode="json")})
    except WebSocketDisconnect:
        logger.info("ws disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.exception("ws_verify error")
        await ws.send_json({"type": "error", "message": str(exc)})
    finally:
        await ws.close()
