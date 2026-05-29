"""FastAPI 应用入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.review import router as review_router
from app.core.config import get_settings

app = FastAPI(
    title="AI PR Review 助手",
    description="指定 GitHub PR，自动获取变更并由 AI 辅助分析。",
    version="0.1.0",
)

# 开发期允许本地前端跨域访问（默认放行 localhost / 127.0.0.1 任意端口）
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=get_settings().cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(review_router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "deepseek_configured": bool(s.deepseek_api_key),
        "github_token_configured": bool(s.github_token),
    }
