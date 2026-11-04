import json
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app import providers
from app.config import EMBEDDING_MODEL
from app.errors import AppError


def fake_profile(role="EMBEDDING"):
    return {
        "role": role,
        "base_url": "https://openrouter.ai/api/v1",
        "model": EMBEDDING_MODEL if role == "EMBEDDING" else "test/fixture",
        "key_cipher": providers.encrypt("fixture-key-not-real"),
        "version": 1,
        "capabilities": {"stream_usage": True},
        "input_price": Decimal(0),
        "output_price": Decimal(0),
        "context_window": 16000,
        "max_output_tokens": 100,
        "is_public": True,
    }


@pytest.fixture
def transport_only(monkeypatch):
    monkeypatch.setattr(providers, "profile", AsyncMock(return_value=fake_profile()))
    monkeypatch.setattr(providers, "start_call", AsyncMock(return_value="fixture-call"))
    finish = AsyncMock()
    monkeypatch.setattr(providers, "finish_call", finish)
    return finish


@respx.mock
async def test_embedding_contract_orders_and_normalizes(transport_only):
    vector = [0.0] * 4096
    vector[0] = 3
    vector[1] = 4
    route = respx.post("https://openrouter.ai/api/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"index": 1, "embedding": vector}, {"index": 0, "embedding": vector}],
                "usage": {"prompt_tokens": 8},
            },
        )
    )
    result = await providers.embed(["one", "two"], True, "owner", "stream", True)
    assert len(result) == 2 and result[0][:2] == [0.6, 0.8]
    payload = json.loads(route.calls[0].request.content)
    assert payload["model"] == EMBEDDING_MODEL
    assert payload["input"][0].startswith("Instruct:") and payload["input"][0].endswith(
        "Query: one"
    )
    assert "input_type" not in payload
    assert payload["provider"]["max_price"]["prompt"] == 0.01
    assert "dimension" not in payload
    assert transport_only.call_args.args[3] == "COMPLETED"


@pytest.mark.parametrize("vector", [[0.0] * 4096, [1.0] * 1536, [float("nan")] * 4096])
@respx.mock
async def test_invalid_embedding_space_fails_without_fallback(transport_only, vector):
    # NaN is deliberately encoded to test provider data validation rather than HTTP JSON encoding.
    content = json.dumps({"data": [{"index": 0, "embedding": vector}]}, allow_nan=True)
    respx.post("https://openrouter.ai/api/v1/embeddings").mock(
        return_value=httpx.Response(200, text=content)
    )
    with pytest.raises(AppError):
        await providers.embed(["one"], False, "owner", "stream", True)
    assert transport_only.call_args.args[3] == "FAILED"


@respx.mock
async def test_embedding_daily_quota_is_explicit_without_echoing_provider_payload(transport_only):
    route = respx.post("https://openrouter.ai/api/v1/embeddings").mock(
        return_value=httpx.Response(
            429, json={"error": {"message": "free-models-per-day private-provider-detail"}}
        )
    )
    with pytest.raises(AppError) as error:
        await providers.embed(["one"], False, "owner", "stream", True)
    assert error.value.code == "EMBEDDING_RATE_LIMITED" and error.value.status == 429
    assert error.value.details == {"scope": "DAILY"}
    assert "private-provider-detail" not in str(error.value)
    assert route.call_count == 1 and transport_only.call_args.args[3] == "FAILED"


@respx.mock
async def test_chat_sse_ignores_private_reasoning_and_keeps_usage(transport_only):
    payload = 'data: {"choices":[{"delta":{"reasoning":"private internal text","content":"Visible answer"}}]}\n\n'
    payload += 'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":3}}\n\ndata: [DONE]\n\n'
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=payload)
    )
    result = [
        piece
        async for piece in providers.chat_stream(
            fake_profile("CHAT"), [{"role": "user", "content": "Question"}], "owner", "stream", True
        )
    ]
    assert result == ["Visible answer"]
    assert transport_only.call_args.args[2]["completion_tokens"] == 3


@respx.mock
async def test_provider_failure_is_explicit_and_not_retried(transport_only):
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(429)
    )
    with pytest.raises(AppError, match="HTTP 429"):
        async for _ in providers.chat_stream(fake_profile("CHAT"), [], "owner", "stream", True):
            pass
    assert route.call_count == 1


@pytest.mark.parametrize(
    "content,reason,expected",
    [
        ("", "length", "OUTPUT_LIMIT"),
        ("Partial answer", "length", "OUTPUT_LIMIT"),
        ("  ", "stop", "EMPTY_COMPLETION"),
    ],
)
@respx.mock
async def test_empty_or_exhausted_answers_fail_and_keep_usage(
    transport_only, content, reason, expected
):
    stream = (
        "data: "
        + json.dumps(
            {"choices": [{"delta": {"reasoning": "private never expose", "content": content}}]}
        )
        + "\n\n"
    )
    stream += "data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": reason}]}) + "\n\n"
    stream += (
        "data: "
        + json.dumps(
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 100,
                    "completion_tokens_details": {
                        "reasoning_tokens": 100 if not content.strip() else 50
                    },
                },
            }
        )
        + "\n\ndata: [DONE]\n\n"
    )
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=stream)
    )
    visible = []
    with pytest.raises(AppError) as error:
        async for piece in providers.chat_stream(fake_profile("CHAT"), [], "owner", "stream", True):
            visible.append(piece)
    assert error.value.code == expected and route.call_count == 1
    assert "".join(visible) == content
    assert transport_only.call_args.args[2]["completion_tokens"] == 100
    assert transport_only.call_args.args[3] == "FAILED"
    completion = transport_only.call_args.kwargs["completion"]
    assert completion["finish_reason"] == reason
    assert completion["visible_characters"] == len(content)
    assert "private never expose" not in str(completion)


@pytest.mark.parametrize("base", ["https://openrouter.ai/api/v1", "https://example.test/v1"])
@respx.mock
async def test_reasoning_setting_is_sent_only_to_supported_transport(transport_only, base):
    profile = fake_profile("CHAT") | {"base_url": base, "capabilities": {"reasoning_mode": "off"}}
    route = respx.post(base + "/chat/completions").mock(
        return_value=httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"Visible answer"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
        )
    )
    assert await providers.complete(profile, [], "owner", "stream", True) == "Visible answer"
    payload = json.loads(route.calls[0].request.content)
    if "openrouter.ai" in base:
        assert payload["reasoning"] == {"enabled": False, "exclude": True}
    else:
        assert "reasoning" not in payload
