from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models.llm import ChatMessage
from app.services.deepseek_client import DeepSeekClient, DeepSeekError


def _settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com",
        deepseek_chat_model="deepseek-chat",
        deepseek_reasoner_model="deepseek-reasoner",
    )


def _fake_response(content: str, *, reasoning: str | None = None, model: str = "deepseek-chat"):
    message = SimpleNamespace(content=content, reasoning_content=reasoning)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


class _FakeCompletions:
    def __init__(self, response=None, error=None, fail_times=0):
        self._response = response
        self._error = error
        self._fail_times = fail_times
        self.calls = 0
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self._error is not None and self.calls <= self._fail_times:
            raise self._error
        return self._response


def _install_fake(client: DeepSeekClient, completions: _FakeCompletions):
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )


async def test_chat_ok():
    client = DeepSeekClient(_settings())
    fake = _FakeCompletions(response=_fake_response("评审让代码更好。"))
    _install_fake(client, fake)

    resp = await client.chat([ChatMessage(role="user", content="hi")])

    assert resp.content == "评审让代码更好。"
    assert resp.model == "deepseek-chat"
    assert resp.usage.total_tokens == 15
    assert fake.last_kwargs["model"] == "deepseek-chat"
    assert fake.last_kwargs["temperature"] == 0.2


async def test_reason_passes_no_temperature_and_reads_reasoning():
    client = DeepSeekClient(_settings())
    fake = _FakeCompletions(
        response=_fake_response("答案", reasoning="先想A再想B", model="deepseek-reasoner")
    )
    _install_fake(client, fake)

    resp = await client.reason([ChatMessage(role="user", content="hi")])

    assert resp.reasoning == "先想A再想B"
    assert fake.last_kwargs["model"] == "deepseek-reasoner"
    assert "temperature" not in fake.last_kwargs


async def test_missing_api_key_raises():
    s = _settings()
    s.deepseek_api_key = ""
    client = DeepSeekClient(s)
    with pytest.raises(DeepSeekError):
        await client.chat([ChatMessage(role="user", content="hi")])


async def test_retry_then_success():
    from openai import APITimeoutError

    client = DeepSeekClient(_settings(), max_retries=3, backoff_base=0.0)
    fake = _FakeCompletions(
        response=_fake_response("ok"),
        error=APITimeoutError(request=None),
        fail_times=2,
    )
    _install_fake(client, fake)

    resp = await client.chat([ChatMessage(role="user", content="hi")])

    assert resp.content == "ok"
    assert fake.calls == 3


async def test_non_retryable_error_wrapped():
    client = DeepSeekClient(_settings())
    fake = _FakeCompletions(error=ValueError("boom"), fail_times=99)
    _install_fake(client, fake)

    with pytest.raises(DeepSeekError):
        await client.chat([ChatMessage(role="user", content="hi")])
