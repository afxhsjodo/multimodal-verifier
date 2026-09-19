"""FastAPI 入口：注册路由、初始化数据库、配置跨域。"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import feedback, verify
from app.core.config import settings
from app.db import database

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(verify.router, tags=["verify"])
app.include_router(feedback.router, tags=["feedback"])

# 幂等初始化数据库（导入即建表，避免依赖 startup 事件）
database.init_db()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "mock_mode": not settings.has_deepseek,
        "has_deepseek": settings.has_deepseek,
        "has_dashscope": settings.has_dashscope,
    }


# 若存在前端构建产物，则挂载静态资源（前端 `npm run build` 后）
_frontend_dist = settings.project_root.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
