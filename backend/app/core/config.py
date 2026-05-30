"""应用配置：从环境变量 / .env 读取。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 默认缓存文件落在 backend 目录下（config.py 在 backend/app/core/ 下，向上三级到 backend/）
_DEFAULT_CACHE_DB = str(Path(__file__).resolve().parents[2] / ".cache.db")


class Settings(BaseSettings):
    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_chat_model: str = "deepseek-chat"
    deepseek_reasoner_model: str = "deepseek-reasoner"

    # GitHub
    github_token: str = ""
    github_api_base: str = "https://api.github.com"

    # 后端服务
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    # 请求超时（秒）
    http_timeout: float = 30.0

    # 分析结果缓存：以 (kind + PR + head_sha) 为 key 缓存 summary / risks 结果
    cache_enabled: bool = True
    cache_db_path: str = _DEFAULT_CACHE_DB

    # CORS：允许的前端来源正则（默认放行 localhost / 127.0.0.1 的任意端口）
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

    model_config = SettingsConfigDict(
        # 优先读取仓库根目录与 backend 目录下的 .env
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
