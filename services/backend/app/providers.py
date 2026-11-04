"""OpenAI-compatible transport, encrypted profiles, and per-attempt accounting."""

import asyncio
import json
import math
import re
from collections.abc import AsyncIterator
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet

from app import db
from app.config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_INPUT_PRICE,
    EMBEDDING_MODEL,
    EMBEDDING_QUERY_INSTRUCTION,
    settings,
)
from app.errors import AppError
from app.events import emit


def cipher() -> Fernet:
    return Fernet(settings().master_key.get_secret_value().encode())


def encrypt(key: str) -> str | None:
    return cipher().encrypt(key.encode()).decode() if key else None


def decrypt(key: str | None) -> str:
    return cipher().decrypt(key.encode()).decode() if key else ""


def validate_base_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AppError(
            "INVALID_BASE_URL", "Use an http(s) API base URL without credentials or a query."
        )
    if parsed.scheme == "http" and not settings().allow_local_providers:
        raise AppError("HTTPS_REQUIRED", "This deployment requires HTTPS providers.")
    return value.rstrip("/")


async def profile(role: str) -> dict:
    row = await db.one("SELECT * FROM model_profiles WHERE role=%s", (role,))
    if not row:
        raise AppError("PROFILE_MISSING", "Provider profile is not configured.", 503)
    return row


def public_profile(row: dict) -> dict:
    return db.serializable(
        {key: value for key, value in row.items() if key != "key_cipher"}
        | {
            "has_key": bool(row.get("key_cipher")),
            "configured": bool(
                row["model"]
                and (row.get("key_cipher") or row.get("capabilities", {}).get("keyless"))
            ),
        }
    )


def token_estimate(text: str) -> int:
    # The estimate is explicitly labelled; provider-reported usage replaces it when present.
    text, images = re.subn(r"data:image/[^;\s]+;base64,[A-Za-z0-9+/=]+", "[image]", text)
    return max(1, math.ceil(len(text.encode()) / 3) + images * 4096)


async def start_call(row: dict, owner: str, stream_id: str, text: str, admin: bool = False) -> str:
    configured = row["model"] and (row["key_cipher"] or row["capabilities"].get("keyless"))
    if not configured:
        raise AppError(
            "PROVIDER_NOT_CONFIGURED",
            f"Configure the {row['role'].lower()} provider in Admin.",
            409,
        )
    if not admin and not row["is_public"]:
        raise AppError(
            "PROVIDER_PRIVATE", "This provider is available to the administrator only.", 403
        )
    if not admin and (row["input_price"] is None or row["output_price"] is None):
        raise AppError(
            "PRICE_REQUIRED", "Public providers require configured input and output pricing.", 409
        )
    call_id = db.new_id()
    amount = (
        (row["input_price"] or 0) * row["context_window"]
        + (row["output_price"] or 0) * row["max_output_tokens"]
    ) / Decimal(1_000_000)
    async with db.connection() as conn:
        await conn.execute("SELECT pg_advisory_xact_lock(76813043)")
        if not admin:
            quota = await (
                await conn.execute(
                    "SELECT count(*) AS calls,coalesce(sum(coalesce(input_tokens,(detail->>'estimated_input_tokens')::int,0)+coalesce(output_tokens,(detail->>'reserved_output_tokens')::int,0)),0) AS tokens FROM provider_calls WHERE owner_id=%s AND started_at>=date_trunc('day',now())",
                    (owner,),
                )
            ).fetchone()
            if (
                quota["calls"] >= settings().guest_model_call_limit
                or quota["tokens"] + token_estimate(text) + row["max_output_tokens"]
                > settings().guest_token_limit
            ):
                raise AppError(
                    "MODEL_QUOTA",
                    "This demo's daily model-call or token limit has been reached.",
                    429,
                )
        source_budget = await (
            await conn.execute(
                "SELECT processing->>'processing_budget_usd' AS budget FROM source_revisions WHERE id=%s",
                (stream_id,),
            )
        ).fetchone()
        if source_budget and source_budget["budget"] is not None:
            reserved = await (
                await conn.execute(
                    "SELECT coalesce(sum(b.amount_usd),0) AS used FROM budget_reservations b JOIN provider_calls p ON p.id=b.id WHERE p.stream_id=%s AND b.status!='RELEASED'",
                    (stream_id,),
                )
            ).fetchone()
            if reserved["used"] + amount > Decimal(source_budget["budget"]):
                raise AppError(
                    "DOCUMENT_BUDGET_EXCEEDED",
                    "This document's processing budget has been reached. Review the partial extraction or increase the budget explicitly.",
                    429,
                )
        budget_row = await (
            await conn.execute("SELECT value FROM app_settings WHERE key='budgets'")
        ).fetchone()
        budgets = (
            budget_row["value"] if budget_row else {"global_daily_usd": 5, "guest_daily_usd": 0.20}
        )
        totals = await (
            await conn.execute(
                "SELECT coalesce(sum(amount_usd),0) AS total, "
                "coalesce(sum(amount_usd) FILTER(WHERE owner_id=%s),0) AS own "
                "FROM budget_reservations WHERE status!='RELEASED' AND created_at>=date_trunc('day',now())",
                (owner,),
            )
        ).fetchone()
        if totals["total"] + amount > Decimal(str(budgets["global_daily_usd"])) or (
            not admin and totals["own"] + amount > Decimal(str(budgets["guest_daily_usd"]))
        ):
            raise AppError(
                "BUDGET_EXCEEDED",
                "The demo inference budget has been reached. Try again tomorrow.",
                429,
            )
        await conn.execute(
            "INSERT INTO provider_calls(id,owner_id,stream_id,role,model,profile_version,detail) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                call_id,
                owner,
                stream_id,
                row["role"],
                row["model"],
                row["version"],
                db.jsonb(
                    {
                        "estimated_input_tokens": token_estimate(text),
                        "reserved_output_tokens": row["max_output_tokens"],
                        "input_price": str(row["input_price"]),
                        "output_price": str(row["output_price"]),
                    }
                ),
            ),
        )
        await conn.execute(
            "INSERT INTO budget_reservations(id,owner_id,amount_usd) VALUES(%s,%s,%s)",
            (call_id, owner, amount),
        )
    await emit(
        owner,
        stream_id,
        "provider.started",
        {
            "call_id": call_id,
            "role": row["role"],
            "model": row["model"],
            "estimated_input_tokens": token_estimate(text),
            "usage_status": "ESTIMATED",
            "input_price_usd_per_million": float(row["input_price"])
            if row["input_price"] is not None
            else None,
            "output_price_usd_per_million": float(row["output_price"])
            if row["output_price"] is not None
            else None,
        },
    )
    return call_id


async def finish_call(
    call_id: str,
    row: dict,
    usage: dict | None,
    status: str,
    owner: str,
    stream_id: str,
    completion: dict | None = None,
) -> None:
    usage = usage or {}
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get(
        "completion_tokens", usage.get("output_tokens", 0 if row["role"] == "EMBEDDING" else None)
    )
    input_tokens = (
        input_tokens if isinstance(input_tokens, int) and 0 <= input_tokens <= 100_000_000 else None
    )
    output_tokens = (
        output_tokens
        if isinstance(output_tokens, int) and 0 <= output_tokens <= 100_000_000
        else None
    )
    cost = usage.get("cost")
    try:
        cost = Decimal(str(cost)) if cost is not None else None
        if cost is not None and (not cost.is_finite() or cost < 0 or cost > 1000):
            cost = None
    except Exception:
        cost = None
    cost_status = "REPORTED" if cost is not None else "UNAVAILABLE"
    if (
        cost is None
        and input_tokens is not None
        and output_tokens is not None
        and row["input_price"] is not None
        and row["output_price"] is not None
    ):
        cost = (
            Decimal(input_tokens) * row["input_price"]
            + Decimal(output_tokens) * row["output_price"]
        ) / Decimal(1_000_000)
        cost_status = "CALCULATED"
    if row["input_price"] == 0 and row["output_price"] == 0:
        cost = Decimal(0)
        cost_status = "CALCULATED"
    async with db.connection() as conn:
        await conn.execute(
            "UPDATE provider_calls SET status=%s,input_tokens=%s,output_tokens=%s,cost_usd=%s,"
            "cost_status=%s,usage_status=%s,detail=detail || %s,finished_at=now() WHERE id=%s",
            (
                status,
                input_tokens,
                output_tokens,
                cost,
                cost_status,
                "REPORTED" if input_tokens is not None else "UNAVAILABLE",
                db.jsonb(completion or {}),
                call_id,
            ),
        )
        if cost is not None:
            await conn.execute(
                "UPDATE budget_reservations SET amount_usd=%s,status='SETTLED' WHERE id=%s",
                (cost, call_id),
            )
        else:
            await conn.execute(
                "UPDATE budget_reservations SET status='UNCERTAIN' WHERE id=%s", (call_id,)
            )
    await emit(
        owner,
        stream_id,
        "provider.finished",
        {
            "call_id": call_id,
            "status": status,
            "role": row["role"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": float(cost) if cost is not None else None,
            "cost_status": cost_status,
            "usage_status": "REPORTED" if input_tokens is not None else "UNAVAILABLE",
            **(completion or {}),
        },
    )


def headers(row: dict) -> dict:
    result = {"Content-Type": "application/json"}
    key = decrypt(row.get("key_cipher"))
    if key:
        result["Authorization"] = f"Bearer {key}"
    if "openrouter.ai" in row["base_url"]:
        result["HTTP-Referer"] = settings().web_origin
        result["X-Title"] = "Tampak-Chat"
    return result


async def chat_stream(
    row: dict, messages: list, owner: str, stream_id: str, admin: bool
) -> AsyncIterator[str | dict]:
    call_id = await start_call(row, owner, stream_id, json.dumps(messages), admin)
    usage = None
    status = "FAILED"
    visible_characters = 0
    has_visible_text = False
    finish_reason = None
    try:
        payload = {
            "model": row["model"],
            "messages": messages,
            "stream": True,
            "max_tokens": row["max_output_tokens"],
        }
        if row["capabilities"].get("stream_usage", True):
            payload["stream_options"] = {"include_usage": True}
        reasoning = row["capabilities"].get("reasoning_mode", "auto")
        if urlparse(row["base_url"]).hostname == "openrouter.ai" and reasoning != "auto":
            payload["reasoning"] = (
                {"enabled": False, "exclude": True}
                if reasoning == "off"
                else {"effort": reasoning, "exclude": True}
            )
        async with httpx.AsyncClient(timeout=settings().provider_timeout) as client:
            async with client.stream(
                "POST", row["base_url"] + "/chat/completions", headers=headers(row), json=payload
            ) as response:
                if response.status_code >= 400:
                    raise AppError(
                        "PROVIDER_ERROR",
                        f"Chat provider returned HTTP {response.status_code}. Check configuration or quota.",
                        502,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    item = json.loads(data)
                    if item.get("error"):
                        raise AppError(
                            "PROVIDER_ERROR", "The provider reported a streaming error.", 502
                        )
                    if item.get("usage"):
                        usage = item["usage"]
                    for choice in item.get("choices", []):
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        delta = choice.get("delta", {}).get("content")
                        if isinstance(delta, str):
                            visible_characters += len(delta)
                            has_visible_text = has_visible_text or bool(delta.strip())
                            yield delta
        if finish_reason == "length":
            raise AppError(
                "OUTPUT_LIMIT",
                "The model reached its output-token limit before completing the answer. Reasoning can consume the same allowance. Increase the output limit or reduce reasoning in Admin, then retry as a new run. This attempt's usage is recorded.",
                502,
            )
        if not has_visible_text:
            raise AppError(
                "EMPTY_COMPLETION",
                "The model returned no answer text. Its usage is recorded; retry as a new run or review the model's output and reasoning settings in Admin.",
                502,
            )
        status = "COMPLETED"
    except asyncio.CancelledError:
        status = "CANCELLED"
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise AppError(
            "PROVIDER_UNAVAILABLE",
            "The provider connection failed. This attempt may have been billed.",
            502,
        ) from error
    finally:
        details = usage.get("completion_tokens_details", {}) if isinstance(usage, dict) else {}
        reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
        completion = {"finish_reason": finish_reason, "visible_characters": visible_characters}
        if isinstance(reasoning_tokens, int) and 0 <= reasoning_tokens <= 100_000_000:
            completion["reasoning_tokens"] = reasoning_tokens
        await finish_call(call_id, row, usage, status, owner, stream_id, completion=completion)


async def complete(row: dict, messages: list, owner: str, stream_id: str, admin: bool) -> str:
    parts = []
    async for piece in chat_stream(row, messages, owner, stream_id, admin):
        if isinstance(piece, str):
            parts.append(piece)
    return "".join(parts)


async def embed(
    texts: list[str], query: bool, owner: str, stream_id: str, admin: bool
) -> list[list[float]]:
    row = await profile("EMBEDDING")
    if row["model"] != EMBEDDING_MODEL or row["base_url"] != "https://openrouter.ai/api/v1":
        raise AppError(
            "EMBEDDING_SPACE_INVALID",
            "The configured embedding space does not match the fixed index.",
            409,
        )
    inputs = [
        f"Instruct: {EMBEDDING_QUERY_INSTRUCTION}\nQuery: {text}" if query else text
        for text in texts
    ]
    call_id = await start_call(row, owner, stream_id, "\n".join(inputs), admin)
    usage = None
    status = "FAILED"
    try:
        async with httpx.AsyncClient(timeout=settings().provider_timeout) as client:
            response = await client.post(
                row["base_url"] + "/embeddings",
                headers=headers(row),
                json={
                    "model": EMBEDDING_MODEL,
                    "input": inputs,
                    "encoding_format": "float",
                    "provider": {"sort": "price", "max_price": {"prompt": EMBEDDING_INPUT_PRICE}},
                },
            )
        if response.status_code == 429:
            try:
                daily = "free-models-per-day" in str(
                    response.json().get("error", {}).get("message", "")
                )
            except (ValueError, AttributeError):
                daily = False
            raise AppError(
                "EMBEDDING_RATE_LIMITED",
                "The embedding provider's daily request quota is exhausted. Lexical retrieval remains available."
                if daily
                else "The embedding provider is rate-limiting requests. Lexical retrieval remains available.",
                429,
                {"scope": "DAILY" if daily else "RATE"},
            )
        if response.status_code >= 400:
            raise AppError(
                "EMBEDDING_ERROR",
                f"Embedding provider returned HTTP {response.status_code}. The pinned model has not been replaced.",
                502,
            )
        payload = response.json()
        usage = payload.get("usage")
        items = sorted(payload.get("data", []), key=lambda x: x["index"])
        vectors = [item["embedding"] for item in items]
        if len(vectors) != len(texts) or [item["index"] for item in items] != list(
            range(len(texts))
        ):
            raise AppError(
                "EMBEDDING_SHAPE", "Embedding response has missing or duplicate items.", 502
            )
        normalized = []
        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS or not all(
                isinstance(x, (int, float)) and math.isfinite(x) for x in vector
            ):
                raise AppError(
                    "EMBEDDING_SHAPE", "The model must return 4096 finite dimensions.", 502
                )
            norm = math.hypot(*vector)
            if not math.isfinite(norm) or norm < 1e-8:
                raise AppError("EMBEDDING_ZERO", "The model returned a zero embedding.", 502)
            normalized.append([x / norm for x in vector])
        status = "COMPLETED"
        return normalized
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise AppError(
            "EMBEDDING_UNAVAILABLE",
            "Embedding failed; this revision remains available for review.",
            502,
        ) from error
    finally:
        await finish_call(call_id, row, usage, status, owner, stream_id)


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"
