from datetime import date

import pytest

from app.analytics import AnalysisPlan, analyze, infer_plan, inspect_records
from app.errors import AppError
from app.ingestion import storage_path


@pytest.mark.parametrize(
    "question",
    [
        "Compare October with September failure rates",
        "Show September versus October failure rates",
        "Bandingkan Oktober dan September tingkat kegagalan",
    ],
)
async def test_named_month_comparison_selects_later_month(seed_dataset, question):
    plan = infer_plan(question, seed_dataset, "2026-10")
    assert plan.start == date(2026, 10, 1) and plan.end == date(2026, 11, 1)
    assert plan.compare_previous
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    assert result["rows"][0]["value"] == 11.1 and result["rows"][0]["previous"] == 3.8


async def test_nonadjacent_explicit_comparison_is_not_silently_reinterpreted(seed_dataset):
    with pytest.raises(AppError) as error:
        infer_plan("Compare August versus October failure rates", seed_dataset, "2026-10")
    assert error.value.code == "COMPARISON_PERIOD_UNSUPPORTED"


@pytest.mark.parametrize("month,expected", [(8, 3.0), (9, 3.8), (10, 11.1)])
async def test_exact_failure_rates_exclude_pending(seed_dataset, month, expected):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]), start=date(2026, month, 1), end=date(2026, month + 1, 1)
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    row = result["rows"][0]
    assert row["value"] == expected
    assert row["completed"] == 10_000 and row["excluded"] == 60


async def test_channel_concentration(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        start=date(2026, 10, 1),
        end=date(2026, 11, 1),
        group_by="channel",
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    wallet = next(row for row in result["rows"] if row["label"] == "E-wallet")
    assert wallet["failed"] == 648 and wallet["completed"] == 4000 and wallet["value"] == 16.2
    assert sum(row["failed"] for row in result["rows"]) == 1110


async def test_empty_period_does_not_fabricate_values(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]), start=date(2025, 1, 1), end=date(2025, 2, 1)
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    assert result["rows"] == []


async def test_count_includes_pending_when_metric_is_volume(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        metric="count",
        start=date(2026, 10, 1),
        end=date(2026, 11, 1),
        group_by="status",
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    assert sum(row["value"] for row in result["rows"]) == 10060
    assert next(row["value"] for row in result["rows"] if row["label"] == "PENDING") == 60


async def test_followup_preserves_period_filter_and_dataset(seed_dataset):
    original = infer_plan(
        "Show daily failure rate for E-wallet in October", seed_dataset, "2026-10"
    )
    follow = infer_plan(
        "Use a line chart instead for the same data",
        seed_dataset,
        "2026-10",
        {"plan": original.model_dump(mode="json")},
    )
    assert follow.start == original.start and follow.end == original.end
    assert (
        follow.channel == "E-wallet"
        and follow.group_by == "day"
        and follow.dataset_id == original.dataset_id
    )


async def test_unknown_column_and_sql_text_rejected(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]), metric="sum", measure="amount); DROP TABLE data;--"
    )
    with pytest.raises(AppError, match="column outside"):
        analyze(
            storage_path(seed_dataset["storage_key"]),
            seed_dataset["schema_info"],
            seed_dataset["mapping"],
            plan,
        )


async def test_source_drilldown_reuses_saved_filters(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        start=date(2026, 10, 1),
        end=date(2026, 11, 1),
        channel="E-wallet",
    )
    result = inspect_records(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    assert result["total_matching"] == 4015 and len(result["records"]) == 100
    assert all(
        str(row["timestamp"]).startswith("2026-10") and row["channel"] == "E-wallet"
        for row in result["records"]
    )


async def test_success_rate_uses_the_same_terminal_denominator(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        metric="success_rate",
        start=date(2026, 10, 1),
        end=date(2026, 11, 1),
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    assert result["rows"][0]["value"] == 88.9 and result["rows"][0]["successful"] == 8890


async def test_month_comparison_distinguishes_percentage_points_and_relative_change(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        start=date(2026, 10, 1),
        end=date(2026, 11, 1),
        compare_previous=True,
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    row = result["rows"][0]
    assert (
        row["previous"] == 3.8
        and row["change"] == 7.3
        and abs(row["relative_change_pct"] - 192.1053) < 0.001
    )
    assert result["comparison"]["start"] == "2026-09-01"


async def test_contribution_is_a_share_of_the_increase_not_the_current_failure_rate(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        metric="failure_contribution",
        start=date(2026, 10, 1),
        end=date(2026, 11, 1),
        group_by="channel",
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    row = result["rows"][0]
    assert row["label"] == "E-wallet" and row["delta_failed"] == 548
    assert abs(row["value"] - 75.0685) < 0.001 and row["current_rate"] == 16.2
    assert result["comparison"]["failure_change"] == 730


async def test_absent_baseline_does_not_turn_into_zero(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        start=date(2026, 8, 1),
        end=date(2026, 9, 1),
        compare_previous=True,
    )
    with pytest.raises(AppError, match="preceding period has no records"):
        analyze(
            storage_path(seed_dataset["storage_key"]),
            seed_dataset["schema_info"],
            seed_dataset["mapping"],
            plan,
        )


async def test_pending_only_group_has_undefined_rate(seed_dataset):
    plan = AnalysisPlan(
        dataset_id=str(seed_dataset["id"]),
        start=date(2026, 10, 1),
        end=date(2026, 11, 1),
        group_by="status",
    )
    result = analyze(
        storage_path(seed_dataset["storage_key"]),
        seed_dataset["schema_info"],
        seed_dataset["mapping"],
        plan,
    )
    pending = next(row for row in result["rows"] if row["label"] == "PENDING")
    assert pending["value"] is None and pending["completed"] == 0 and pending["excluded"] == 60


def test_timezone_conversion_respects_month_boundaries(tmp_path):
    import duckdb

    path = tmp_path / "timezone.parquet"
    conn = duckdb.connect()
    conn.execute("CREATE TABLE data(timestamp VARCHAR,status VARCHAR,channel VARCHAR,amount INT)")
    conn.execute(
        "INSERT INTO data VALUES ('2026-10-31T23:30:00Z','FAILED','Wallet',1),('2026-10-31T16:00:00Z','SUCCESS','Wallet',1)"
    )
    conn.execute("COPY data TO ? (FORMAT PARQUET)", [str(path)])
    conn.close()
    schema = {"columns": [{"name": name} for name in ["timestamp", "status", "channel", "amount"]]}
    mapping = {
        "timestamp": "timestamp",
        "status": "status",
        "channel": "channel",
        "amount": "amount",
        "success_values": ["SUCCESS"],
        "failed_values": ["FAILED"],
    }
    result = analyze(
        path,
        schema,
        mapping,
        AnalysisPlan(dataset_id="fixture", start=date(2026, 10, 1), end=date(2026, 11, 1)),
    )
    assert result["rows"][0]["completed"] == 1 and result["rows"][0]["value"] == 0


def test_explicit_day_first_date_mapping(tmp_path):
    import duckdb

    path = tmp_path / "dates.parquet"
    conn = duckdb.connect()
    conn.execute("CREATE TABLE data(timestamp VARCHAR,status VARCHAR)")
    conn.execute("INSERT INTO data VALUES ('03/10/2026','SUCCESS'),('04/10/2026','FAILED')")
    conn.execute("COPY data TO ? (FORMAT PARQUET)", [str(path)])
    conn.close()
    schema = {"columns": [{"name": "timestamp"}, {"name": "status"}]}
    mapping = {
        "timestamp": "timestamp",
        "status": "status",
        "date_format": "%d/%m/%Y",
        "success_values": ["SUCCESS"],
        "failed_values": ["FAILED"],
    }
    result = analyze(
        path,
        schema,
        mapping,
        AnalysisPlan(dataset_id="fixture", start=date(2026, 10, 1), end=date(2026, 11, 1)),
    )
    assert result["rows"][0]["value"] == 50


@pytest.mark.parametrize(
    "field,value",
    [("metric", "arbitrary_sql"), ("group_by", "read_csv('/etc/passwd')"), ("chart", "javascript")],
)
def test_tool_plan_rejects_unsupported_operations(field, value):
    with pytest.raises(ValueError):
        AnalysisPlan.model_validate({"dataset_id": "test", field: value})
