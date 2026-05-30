"""DeepSeek 客户端封装。

DeepSeek 提供 OpenAI 兼容接口，因此直接复用 openai SDK，仅替换 base_url。
对外暴露两个语义入口：
- chat()      使用 deepseek-chat（V3）：快、便宜，用于变更总结与全量 hunk 分诊
- reason()    使用 deepseek-reasoner（R1）：推理强，用于高风险点深度复查

内置指数退避重试，处理限流与瞬时网络错误。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.core.config import Settings, get_settings
from app.models.llm import ChatMessage, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)

_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError)


@dataclass
class ChatStreamChunk:
    """流式调用的一个增量：delta 为新增文本片段；结束块 done=True 并带最终 usage/model。"""

    delta: str = ""
    done: bool = False
    usage: TokenUsage | None = None
    model: str = ""


class DeepSeekError(RuntimeError):
    """DeepSeek 调用相关错误。"""


class DeepSeekClient:
    """对 DeepSeek（OpenAI 兼容）接口的薄封装。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        self._settings = settings or get_settings()
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        # 延迟构造：AsyncOpenAI 在缺少 api_key 时会于构造期抛错，
        # 而我们希望把“未配置 key”表达为可读的 DeepSeekError，故首次调用时再建。
        self._client: AsyncOpenAI | None = None

    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._settings.deepseek_api_key,
                base_url=self._settings.deepseek_base_url,
                timeout=self._settings.http_timeout,
            )
        return self._client

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """使用 deepseek-chat（V3）。"""
        return await self._complete(
            model=self._settings.deepseek_chat_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatStreamChunk]:
        """流式调用 deepseek-chat（V3），逐 token 产出 ChatStreamChunk。

        建连阶段（首个 chunk 到达前）的可重试错误会退避重试；一旦开始产出 delta
        就不再重试（避免重复输出）。最后产出一个 done=True 的结束块携带 usage。
        """
        if not self._settings.deepseek_api_key:
            raise DeepSeekError("未配置 DEEPSEEK_API_KEY，无法调用模型")

        payload: dict = {
            "model": self._settings.deepseek_chat_model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "stream": True,
            # 流式默认不带 usage，显式要求在结束块返回
            "stream_options": {"include_usage": True},
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async for chunk in self._stream_once(payload):
                    yield chunk
                return
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    break
                delay = self._backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    "DeepSeek 流式建连失败(%s)，第 %d/%d 次重试，%.1fs 后重试",
                    type(exc).__name__,
                    attempt,
                    self._max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
            except DeepSeekError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise DeepSeekError(f"DeepSeek 流式调用失败：{exc}") from exc

        raise DeepSeekError(
            f"DeepSeek 流式调用在 {self._max_retries} 次重试后仍失败：{last_exc}"
        ) from last_exc

    async def _stream_once(
        self, payload: dict
    ) -> AsyncIterator[ChatStreamChunk]:
        """单次流式请求：建连后逐块产出；建连前的异常向上传播以触发重试。

        一旦产出过 delta，内部异常包装为 DeepSeekError 直接抛出（不重试）。
        """
        client = self._ensure_client()
        stream = await client.chat.completions.create(**payload)
        started = False
        model = payload["model"]
        usage = TokenUsage()
        try:
            async for event in stream:
                if getattr(event, "model", None):
                    model = event.model
                if event.usage is not None:
                    usage = TokenUsage(
                        prompt_tokens=event.usage.prompt_tokens or 0,
                        completion_tokens=event.usage.completion_tokens or 0,
                        total_tokens=event.usage.total_tokens or 0,
                    )
                if not event.choices:
                    continue
                delta = event.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    started = True
                    yield ChatStreamChunk(delta=text)
        except _RETRYABLE:
            if started:
                raise DeepSeekError("DeepSeek 流式中断，已输出部分内容")
            raise
        except Exception as exc:  # noqa: BLE001
            raise DeepSeekError(f"DeepSeek 流式调用失败：{exc}") from exc

        yield ChatStreamChunk(done=True, usage=usage, model=model)

    async def reason(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """使用 deepseek-reasoner（R1）。

        注意：reasoner 不支持 temperature 等采样参数，这里不传。
        """
        return await self._complete(
            model=self._settings.deepseek_reasoner_model,
            messages=messages,
            temperature=None,
            max_tokens=max_tokens,
        )

    async def _complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float | None,
        max_tokens: int | None,
    ) -> LLMResponse:
        if not self._settings.deepseek_api_key:
            raise DeepSeekError("未配置 DEEPSEEK_API_KEY，无法调用模型")

        client = self._ensure_client()

        payload: dict = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await client.chat.completions.create(**payload)
                return self._parse(resp, model)
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    break
                delay = self._backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    "DeepSeek 调用失败(%s)，第 %d/%d 次重试，%.1fs 后重试",
                    type(exc).__name__,
                    attempt,
                    self._max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
            except Exception as exc:  # noqa: BLE001 非可重试错误直接包装抛出
                raise DeepSeekError(f"DeepSeek 调用失败：{exc}") from exc

        raise DeepSeekError(
            f"DeepSeek 调用在 {self._max_retries} 次重试后仍失败：{last_exc}"
        ) from last_exc

    @staticmethod
    def _parse(resp, model: str) -> LLMResponse:
        choice = resp.choices[0]
        message = choice.message
        content = message.content or ""
        # reasoner 模型在 reasoning_content 字段返回思维链
        reasoning = getattr(message, "reasoning_content", None)

        usage = TokenUsage()
        if resp.usage is not None:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens or 0,
                completion_tokens=resp.usage.completion_tokens or 0,
                total_tokens=resp.usage.total_tokens or 0,
            )

        return LLMResponse(
            content=content,
            model=getattr(resp, "model", model),
            reasoning=reasoning,
            usage=usage,
        )
