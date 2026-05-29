"""应用配置：从环境变量 / .env 读取。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
