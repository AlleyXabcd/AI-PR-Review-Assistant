"""LLM（DeepSeek）相关数据模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """一条对话消息。"""

    role: str  # system / user / assistant
    content: str


class TokenUsage(BaseModel):
    """单次调用的 token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """一次 LLM 调用的结构化结果。"""

    content: str
    model: str
    # reasoner 模型（R1）会返回思维链，chat 模型为空
    reasoning: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
