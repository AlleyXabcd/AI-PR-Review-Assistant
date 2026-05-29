"""手动验证脚本：用真实 DEEPSEEK_API_KEY 调一次对话。

用法：
    cd backend
    python -m app.scripts.try_deepseek            # 默认 chat(V3)
    python -m app.scripts.try_deepseek --reason   # reasoner(R1)
"""
from __future__ import annotations

import asyncio
import sys

from app.models.llm import ChatMessage
from app.services.deepseek_client import DeepSeekClient, DeepSeekError


async def _run(use_reason: bool) -> int:
    client = DeepSeekClient()
    messages = [
        ChatMessage(role="system", content="你是一个简洁的助手，用一句话回答。"),
        ChatMessage(role="user", content="用中文说一句关于代码评审的话。"),
    ]
    try:
        if use_reason:
            print("调用 deepseek-reasoner (R1) ...")
            resp = await client.reason(messages)
        else:
            print("调用 deepseek-chat (V3) ...")
            resp = await client.chat(messages)
    except DeepSeekError as exc:
        print(f"[调用失败] {exc}")
        return 1

    print(f"\n模型: {resp.model}")
    if resp.reasoning:
        print(f"思维链: {resp.reasoning[:200]}...")
    print(f"回复: {resp.content}")
    print(
        f"用量: prompt={resp.usage.prompt_tokens} "
        f"completion={resp.usage.completion_tokens} "
        f"total={resp.usage.total_tokens}"
    )
    return 0


def main() -> None:
    use_reason = "--reason" in sys.argv[1:]
    raise SystemExit(asyncio.run(_run(use_reason)))


if __name__ == "__main__":
    main()
