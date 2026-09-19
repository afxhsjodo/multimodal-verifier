"""集中配置：从环境变量 / .env 读取，统一密钥、模型名与运行模式。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- DeepSeek 文本/推理 ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_chat_model: str = "deepseek-chat"
    deepseek_reasoner_model: str = "deepseek-reasoner"

    # ---- DashScope：Qwen-VL 视觉 + embedding ----
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_vl_model: str = "qwen-vl-max"
    qwen_embed_model: str = "text-embedding-v3"

    # ---- 网页检索 ----
    tavily_api_key: str = ""
    web_search_provider: str = "tavily"  # tavily | duckduckgo | both

    # ---- 向量库 / 语料 ----
    chroma_dir: str = "./data/chroma"
    corpus_dir: str = "./data/corpus"
    chroma_collection: str = "evidence_corpus"

    # ---- 应用 ----
    app_name: str = "多模态信息核验系统"
    log_level: str = "INFO"

    @property
    def has_deepseek(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def has_dashscope(self) -> bool:
        return bool(self.dashscope_api_key)

    @property
    def has_llm(self) -> bool:
        """是否至少有一个可用 LLM 后端。两个都空则进入 mock 模式。"""
        return self.has_deepseek or self.has_dashscope

    @property
    def project_root(self) -> Path:
        """backend 目录的绝对路径（app/core/config.py 的上三层）。"""
        return Path(__file__).resolve().parent.parent.parent

    def resolved_chroma_dir(self) -> Path:
        p = Path(self.chroma_dir)
        return p if p.is_absolute() else self.project_root / p

    def resolved_corpus_dir(self) -> Path:
        p = Path(self.corpus_dir)
        return p if p.is_absolute() else self.project_root / p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
