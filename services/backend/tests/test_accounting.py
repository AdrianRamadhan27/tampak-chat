from decimal import Decimal

import pytest

from app import db, providers
from app.errors import AppError


def profile():
    return {
        "role": "CHAT",
        "base_url": "https://example.test/v1",
        "model": "test/ledger-fixture",
        "key_cipher": providers.encrypt("not-a-real-key"),
        "version": 7,
        "capabilities": {},
        "is_public": True,
        "input_price": Decimal(1),
        "output_price": Decimal(2),
        "context_window": 16000,
        "max_output_tokens": 100,
    }


async def test_budget_reservation_reconciles_to_actual_reported_tokens(client):
    config = profile()
    stream = db.new_id()
    call = await providers.start_call(config, client.principal_id, stream, "A fixture question.")
    before = await db.one("SELECT * FROM budget_reservations WHERE id=%s", (call,))
    assert before["amount_usd"] == Decimal("0.0162")
    await providers.finish_call(
        call,
        config,
        {"prompt_tokens": 1000, "completion_tokens": 50},
        "COMPLETED",
        client.principal_id,
        stream,
    )
    after = await db.one("SELECT * FROM budget_reservations WHERE id=%s", (call,))
    recorded = await db.one("SELECT * FROM provider_calls WHERE id=%s", (call,))
    assert after["status"] == "SETTLED" and after["amount_usd"] == Decimal("0.0011")
    assert recorded["profile_version"] == 7 and recorded["usage_status"] == "REPORTED"
    assert recorded["cost_status"] == "CALCULATED"


async def test_missing_usage_preserves_uncertain_reservation_instead_of_free_call(client):
    config = profile()
    stream = db.new_id()
    call = await providers.start_call(config, client.principal_id, stream, "Provider timed out.")
    await providers.finish_call(call, config, None, "FAILED", client.principal_id, stream)
    recorded = await db.one("SELECT * FROM provider_calls WHERE id=%s", (call,))
    reserved = await db.one("SELECT * FROM budget_reservations WHERE id=%s", (call,))
    assert recorded["input_tokens"] is None and recorded["cost_usd"] is None
    assert recorded["usage_status"] == recorded["cost_status"] == "UNAVAILABLE"
    assert reserved["status"] == "UNCERTAIN" and reserved["amount_usd"] > 0


async def test_unknown_pricing_blocks_public_request_before_call_is_recorded(client):
    config = profile() | {"input_price": None}
    with pytest.raises(AppError, match="pricing"):
        await providers.start_call(config, client.principal_id, db.new_id(), "Question")
    count = await db.one(
        "SELECT count(*) AS n FROM provider_calls WHERE owner_id=%s", (client.principal_id,)
    )
    assert count["n"] == 0
