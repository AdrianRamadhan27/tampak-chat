"""Typed analysis plans compile to a small allowlist of parameterized DuckDB queries."""

import calendar
import json
import re
from datetime import date
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, Field, model_validator

from app.errors import AppError


def database() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(
        ":memory:",
        config={
            "memory_limit": "256MB",
            "threads": 2,
            "enable_external_access": True,
            "allow_unsigned_extensions": False,
        },
    )
    conn.execute("SET TimeZone='Asia/Jakarta'")
    return conn


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


DATE_FORMATS = {
    "auto",
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M:%S",
}


def timestamp_expression(column: str, mapping: dict) -> str:
    selected = mapping.get("date_format", "auto")
    if selected not in DATE_FORMATS:
        raise AppError(
            "DATE_FORMAT_INVALID", "Select a supported date format in the dataset mapping.", 409
        )
    raw = (
        f"try_cast({column} AS TIMESTAMPTZ)"
        if selected == "auto"
        else f"try_cast(try_strptime(cast({column} AS VARCHAR),'{selected}') AS TIMESTAMPTZ)"
    )
    return f"timezone('Asia/Jakarta',{raw})"


def profile_file(path: Path, folder: Path) -> dict:
    conn = database()
    try:
        if path.suffix.lower() == ".xlsx":
            import openpyxl
            import pyarrow as pa

            workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
            sheet = workbook.active
            if sheet is None:
                raise ValueError("Workbook has no active sheet.")
            rows = sheet.iter_rows(values_only=True)
            header = [str(cell or f"column_{i + 1}") for i, cell in enumerate(next(rows))]
            if len(header) > 80 or len(set(header)) != len(header):
                raise ValueError("Use at most 80 distinct column names.")
            columns: dict[str, list] = {name: [] for name in header}
            for count, row in enumerate(rows):
                if count >= 100_000:
                    raise ValueError("Dataset exceeds 100,000 rows.")
                for name, value in zip(header, row, strict=False):
                    columns[name].append(str(value) if value is not None else None)
            workbook.close()
            conn.register("raw", pa.table(columns))
            conn.execute("CREATE TABLE data AS SELECT * FROM raw")
        else:
            conn.execute(
                "CREATE TABLE data AS SELECT * FROM read_csv(?,header=true,"
                "sample_size=20000,maximum_line_size=1048576)",
                [str(path)],
            )
        count = conn.execute("SELECT count(*) FROM data").fetchone()[0]
        description = conn.execute("DESCRIBE data").fetchall()
        if (
            count > 100_000
            or len(description) > 80
            or count == 0
            or any(len(column[0]) > 100 for column in description)
        ):
            raise ValueError("Use a dataset with 1–100,000 rows and at most 80 columns.")
        if len(set(row[0].lower() for row in description)) != len(description):
            raise ValueError("Column names must be distinct.")
        columns = []
        for name, type_name, *_ in description:
            examples = conn.execute(
                f"SELECT DISTINCT cast({quote(name)} AS VARCHAR) FROM data WHERE {quote(name)} IS NOT NULL LIMIT 5"
            ).fetchall()
            columns.append(
                {"name": name, "type": type_name, "examples": [row[0][:160] for row in examples]}
            )
        sample = [
            dict(zip([c["name"] for c in columns], row, strict=True))
            for row in conn.execute("SELECT * FROM data LIMIT 12").fetchall()
        ]
        parquet = folder / "dataset.parquet"
        conn.execute("COPY data TO ? (FORMAT PARQUET)", [str(parquet)])
        mapping = suggest_mapping(columns)
        text = f"Dataset {path.name}: {count:,} rows. Columns: " + ", ".join(
            c["name"] for c in columns
        )
        return {
            "format": "dataset",
            "parser": "duckdb/openpyxl",
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        {"id": "dataset-schema", "type": "text", "text": text, "bbox": None}
                    ],
                }
            ],
            "warnings": [
                "Confirm semantic mapping before analysis. Numeric answers use exact dataset queries."
            ],
            "dataset": {
                "row_count": count,
                "columns": columns,
                "sample": json.loads(json.dumps(sample, default=str)),
                "mapping": mapping,
                "parquet": "dataset.parquet",
            },
        }
    finally:
        conn.close()


def suggest_mapping(columns: list[dict]) -> dict:
    names = {c["name"].lower(): c["name"] for c in columns}
    choices = {
        "timestamp": ["timestamp", "created_at", "date", "transaction_date", "waktu"],
        "status": ["status", "transaction_status"],
        "channel": ["channel", "payment_channel", "channel_name"],
        "amount": ["amount", "value", "revenue", "nominal"],
    }
    return {
        key: next((names[name] for name in candidates if name in names), None)
        for key, candidates in choices.items()
    } | {"success_values": ["SUCCESS"], "failed_values": ["FAILED"], "pending_values": ["PENDING"]}


class Mapping(BaseModel):
    timestamp: str | None = None
    status: str | None = None
    channel: str | None = None
    amount: str | None = None
    date_format: Literal[
        "auto",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M:%S",
    ] = "auto"
    success_values: list[str] = Field(default_factory=lambda: ["SUCCESS"], max_length=20)
    failed_values: list[str] = Field(default_factory=lambda: ["FAILED"], max_length=20)
    pending_values: list[str] = Field(default_factory=lambda: ["PENDING"], max_length=20)


class AnalysisPlan(BaseModel):
    dataset_id: str
    metric: Literal[
        "failure_rate", "success_rate", "failure_contribution", "count", "sum", "average"
    ] = "failure_rate"
    group_by: Literal["month", "day", "channel", "status", "none"] = "month"
    start: date | None = None
    end: date | None = None  # exclusive
    channel: str | None = Field(default=None, max_length=160)
    measure: str | None = None
    chart: Literal["bar", "line", "area", "pie"] = "bar"
    compare_previous: bool = False

    @model_validator(mode="after")
    def check_dates(self):
        if self.start and self.end and self.start >= self.end:
            raise ValueError("The start date must precede the exclusive end date.")
        return self


def infer_plan(
    question: str, dataset: dict, reference_month: str, context: dict | None = None
) -> AnalysisPlan:
    q = question.lower()
    previous = (context or {}).get("plan", {})
    year, month = [int(part) for part in reference_month.split("-")]
    start = date(year, month, 1)
    end = date(year + month // 12, month % 12 + 1, 1)
    if previous:
        start = date.fromisoformat(previous["start"]) if previous.get("start") else start
        end = date.fromisoformat(previous["end"]) if previous.get("end") else end
    month_names = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    month_names.update(
        {
            "agustus": 8,
            "september": 9,
            "oktober": 10,
            "november": 11,
            "desember": 12,
            "januari": 1,
            "februari": 2,
            "maret": 3,
            "april": 4,
            "mei": 5,
            "juni": 6,
            "juli": 7,
        }
    )
    named_months = {number for name, number in month_names.items() if re.search(rf"\b{name}\b", q)}
    comparing = any(
        word in q
        for word in ["compare", "comparison", "versus", "vs ", "banding", "bulan sebelumnya"]
    )
    if comparing and len(named_months) > 1:
        if len(named_months) != 2 or max(named_months) - min(named_months) != 1:
            raise AppError(
                "COMPARISON_PERIOD_UNSUPPORTED",
                "This comparison tool supports adjacent months. Choose a current month and its preceding month.",
                422,
            )
        selected = max(named_months)
    else:
        selected = next(
            (number for name, number in month_names.items() if re.search(rf"\b{name}\b", q)), None
        )
    if selected:
        start = date(year, selected, 1)
        end = date(year + selected // 12, selected % 12 + 1, 1)
    group = "month"
    if any(word in q for word in ["trend", "trends", "tren", "3 month", "three month", "quarter"]):
        group = "month"
        start = date(year if month > 2 else year - 1, (month - 3) % 12 + 1, 1)
    if any(word in q for word in ["channel", "kanal", "payment method"]):
        group = "channel"
    if any(word in q for word in ["daily", "day", "harian", "date", "tanggal"]):
        group = "day"
    if any(word in q for word in ["status breakdown", "by status"]):
        group = "status"
    channel = previous.get("channel")
    for name in ["E-wallet", "Bank transfer", "QRIS", "Card"]:
        if name.lower() in q or (name == "E-wallet" and "ewallet" in q):
            channel = name
    if any(word in q for word in ["all channels", "semua kanal", "clear filter"]):
        channel = None
    if previous and any(
        word in q for word in ["same", "instead", "chart", "visual", "pie", "line", "bar", "area"]
    ):
        group = previous.get("group_by", group)
    metric = previous.get("metric", "failure_rate") if previous else "failure_rate"
    if any(
        word in q
        for word in ["total transaction", "transaction count", "volume", "jumlah transaksi"]
    ):
        metric = "count"
    if any(word in q for word in ["revenue", "total amount", "sum of", "total nilai"]):
        metric = "sum"
    if any(word in q for word in ["average amount", "average value", "rata-rata"]):
        metric = "average"
    if any(word in q for word in ["failure", "failed", "gagal"]):
        metric = "failure_rate"
    if any(word in q for word in ["success rate", "successful rate", "tingkat keberhasilan"]):
        metric = "success_rate"
    if any(word in q for word in ["contribut", "kontribusi"]) and any(
        word in q for word in ["increase", "change", "peningkatan", "kenaikan"]
    ):
        metric = "failure_contribution"
        group = "channel"
    chart = next(
        (kind for kind in ["pie", "line", "area", "bar"] if kind in q),
        "line" if group in {"month", "day"} else "bar",
    )
    return AnalysisPlan(
        dataset_id=str(dataset["id"]),
        metric=metric,
        group_by=group,
        start=start,
        end=end,
        channel=channel,
        chart=chart,
        compare_previous=comparing or previous.get("compare_previous", False) and "same" in q,
    )


def analyze_base(path: Path, schema: dict, mapping: dict, plan: AnalysisPlan) -> dict:
    names = {column["name"] for column in schema["columns"]}
    for value in [
        mapping.get("timestamp"),
        mapping.get("status"),
        mapping.get("channel"),
        mapping.get("amount"),
        plan.measure,
    ]:
        if value and value not in names:
            raise AppError(
                "COLUMN_INVALID", "The analysis refers to a column outside this dataset."
            )

    def column(key: str) -> str:
        value = mapping.get(key)
        if not value:
            raise AppError(
                "MAPPING_REQUIRED", f"Map the {key} column in the dataset review first.", 409
            )
        return quote(value)

    conn = database()
    try:
        # Load only the server-selected parquet, then disable further filesystem access.
        conn.execute("CREATE TABLE data AS SELECT * FROM read_parquet(?)", [str(path)])
        conn.execute("SET enable_external_access=false")
        params: list = []
        where = ["true"]
        if plan.start or plan.end:
            timestamp = timestamp_expression(column("timestamp"), mapping)
            invalid = conn.execute(
                f"SELECT count(*) FROM data WHERE {column('timestamp')} IS NOT NULL AND {timestamp} IS NULL"
            ).fetchone()[0]
            if invalid:
                raise AppError(
                    "DATE_PARSE_FAILED",
                    f"{invalid} timestamps could not be parsed. Correct the source before analysis.",
                    409,
                )
            if plan.start:
                where.append(f"{timestamp}>=?")
                params.append(plan.start)
            if plan.end:
                where.append(f"{timestamp}<?")
                params.append(plan.end)
        if plan.channel:
            where.append(f"lower(cast({column('channel')} AS VARCHAR))=lower(?)")
            params.append(plan.channel)
        if plan.group_by in {"day", "month"}:
            group = f"strftime({timestamp_expression(column('timestamp'), mapping)},'{'%Y-%m-%d' if plan.group_by == 'day' else '%Y-%m'}')"
        elif plan.group_by in {"channel", "status"}:
            group = f"cast({column(plan.group_by)} AS VARCHAR)"
        else:
            group = "'Total'"
        if plan.metric in {"failure_rate", "success_rate"}:
            status = f"upper(cast({column('status')} AS VARCHAR))"
            failed = [str(value).upper() for value in mapping.get("failed_values", [])]
            success = [str(value).upper() for value in mapping.get("success_values", [])]
            if not failed or not success or set(failed) & set(success):
                raise AppError(
                    "STATUS_MAPPING_REQUIRED",
                    "Map distinct successful and failed status values.",
                    409,
                )
            placeholders = ",".join("?" for _ in failed)
            completed = ",".join("?" for _ in failed + success)
            select = (
                f"count(*) FILTER(WHERE {status} IN ({placeholders})) AS failed, "
                f"count(*) FILTER(WHERE {status} IN ({completed})) AS completed, "
                "count(*) AS total"
            )
            select_params = failed + failed + success
        elif plan.metric in {"sum", "average"}:
            measure = quote(plan.measure) if plan.measure else column("amount")
            invalid = conn.execute(
                f"SELECT count(*) FROM data WHERE {measure} IS NOT NULL AND try_cast({measure} AS DOUBLE) IS NULL"
            ).fetchone()[0]
            if invalid:
                raise AppError(
                    "NUMERIC_PARSE_FAILED",
                    f"{invalid} values are not numeric. Correct the mapping or source.",
                    409,
                )
            select = f"{'sum' if plan.metric == 'sum' else 'avg'}(try_cast({measure} AS DOUBLE)) AS value, count(*) AS total"
            select_params = []
        else:
            select = "count(*) AS value, count(*) AS total"
            select_params = []
        query = f"SELECT {group} AS label,{select} FROM data WHERE {' AND '.join(where)} GROUP BY 1 ORDER BY 1 LIMIT 101"
        cursor = conn.execute(query, select_params + params)
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, row, strict=True)) for row in cursor.fetchall()]
        if len(rows) > 100:
            raise AppError("RESULT_TOO_LARGE", "Narrow the date range to at most 100 groups.", 409)
        for row in rows:
            if plan.metric in {"failure_rate", "success_rate"}:
                row["successful"] = row["completed"] - row["failed"]
                row["value"] = (
                    round(
                        100
                        * row["failed" if plan.metric == "failure_rate" else "successful"]
                        / row["completed"],
                        4,
                    )
                    if row["completed"]
                    else None
                )
                row["excluded"] = row["total"] - row["completed"]
        return {
            "rows": rows,
            "metric": plan.metric,
            "group_by": plan.group_by,
            "unit": "%"
            if plan.metric in {"failure_rate", "success_rate"}
            else "count"
            if plan.metric == "count"
            else "value",
            "definition": f"{'Failed' if plan.metric == 'failure_rate' else 'Successful'} / (successful + failed) × 100; pending and unknown statuses excluded."
            if plan.metric in {"failure_rate", "success_rate"}
            else f"Exact {plan.metric} over mapped dataset values.",
            "period": {
                "start": str(plan.start) if plan.start else None,
                "end_exclusive": str(plan.end) if plan.end else None,
            },
            "filters": {"channel": plan.channel},
            "query_template": query,
            "parameters": [str(p) for p in select_params + params],
            "timezone": "Asia/Jakarta",
            "row_limit": 100,
        }
    finally:
        conn.close()


def prior_period(plan: AnalysisPlan) -> tuple[date, date]:
    if not plan.start or not plan.end:
        raise AppError(
            "COMPARISON_PERIOD_REQUIRED",
            "Choose a start and end date for a period comparison.",
            409,
        )
    if plan.start.day == plan.end.day == 1:
        months = (plan.end.year - plan.start.year) * 12 + plan.end.month - plan.start.month
        offset = plan.start.year * 12 + plan.start.month - 1 - months
        return date(offset // 12, offset % 12 + 1, 1), plan.start
    return plan.start - (plan.end - plan.start), plan.start


def analyze(path: Path, schema: dict, mapping: dict, plan: AnalysisPlan) -> dict:
    contribution = plan.metric == "failure_contribution"
    current_plan = plan.model_copy(
        update={
            "metric": "failure_rate" if contribution else plan.metric,
            "compare_previous": False,
        }
    )
    current = analyze_base(path, schema, mapping, current_plan)
    if not contribution and not plan.compare_previous:
        return current
    start, end = prior_period(plan)
    baseline = analyze_base(
        path, schema, mapping, current_plan.model_copy(update={"start": start, "end": end})
    )
    if not baseline["rows"]:
        raise AppError(
            "BASELINE_UNAVAILABLE",
            "The preceding period has no records in this dataset. Add baseline data or choose a later comparison period.",
            409,
        )
    lookup = {row["label"]: row for row in baseline["rows"]}
    total_change = sum(row.get("failed", 0) for row in current["rows"]) - sum(
        row.get("failed", 0) for row in baseline["rows"]
    )
    for index, row in enumerate(current["rows"]):
        # Time-series comparisons align period positions; category comparisons retain their label.
        previous = (
            baseline["rows"][index]
            if plan.group_by in {"month", "day"} and index < len(baseline["rows"])
            else lookup.get(row["label"])
        )
        row["previous"] = previous.get("value") if previous else None
        row["previous_label"] = previous["label"] if previous else None
        row["change"] = (
            round(row["value"] - row["previous"], 4)
            if row.get("value") is not None and row["previous"] is not None
            else None
        )
        row["relative_change_pct"] = (
            round(100 * row["change"] / row["previous"], 4)
            if row["previous"] and row["change"] is not None
            else None
        )
        if contribution:
            row["previous_failed"] = previous["failed"] if previous else None
            row["delta_failed"] = row["failed"] - previous["failed"] if previous else None
            row["current_rate"] = row["value"]
            row["value"] = (
                round(100 * row["delta_failed"] / total_change, 4)
                if total_change and row["delta_failed"] is not None
                else None
            )
    current["comparison"] = {
        "start": str(start),
        "end_exclusive": str(end),
        "definition": "Changes in rates are percentage points; relative change divides by the baseline. Missing baseline groups remain undefined.",
        "failure_change": total_change if contribution else None,
    }
    if contribution:
        current.update(
            metric="failure_contribution",
            unit="%",
            definition="Channel change in failed transactions / total change in failed transactions × 100. Negative contributions offset increases; a zero total change is undefined.",
        )
        current["rows"].sort(
            key=lambda row: row["value"] if row["value"] is not None else float("-inf"),
            reverse=True,
        )
    return current


def inspect_records(path: Path, schema: dict, mapping: dict, plan: AnalysisPlan) -> dict:
    """A bounded source preview using exactly the saved analysis period and channel filter."""
    names = {column["name"] for column in schema["columns"]}

    def mapped(key):
        value = mapping.get(key)
        if not value or value not in names:
            raise AppError(
                "MAPPING_REQUIRED", f"Map the {key} column before inspecting these records.", 409
            )
        return quote(value)

    where, params = ["true"], []
    if plan.start:
        where.append(f"{timestamp_expression(mapped('timestamp'), mapping)}>=?")
        params.append(plan.start)
    if plan.end:
        where.append(f"{timestamp_expression(mapped('timestamp'), mapping)}<?")
        params.append(plan.end)
    if plan.channel:
        where.append(f"lower(cast({mapped('channel')} AS VARCHAR))=lower(?)")
        params.append(plan.channel)
    conn = database()
    try:
        conn.execute(
            "CREATE TABLE data AS SELECT row_number() OVER() AS _source_record,* FROM read_parquet(?)",
            [str(path)],
        )
        conn.execute("SET enable_external_access=false")
        predicate = " AND ".join(where)
        count = conn.execute(f"SELECT count(*) FROM data WHERE {predicate}", params).fetchone()[0]
        cursor = conn.execute(
            f"SELECT * FROM data WHERE {predicate} ORDER BY _source_record LIMIT 100", params
        )
        columns = [column[0] for column in cursor.description]
        records = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        return {
            "columns": columns,
            "records": json.loads(json.dumps(records, default=str)),
            "total_matching": count,
            "limit": 100,
            "note": "Source record numbers are 1-based record positions. Preview includes pending/unknown statuses; failure-rate denominators exclude them.",
            "period": {
                "start": str(plan.start) if plan.start else None,
                "end_exclusive": str(plan.end) if plan.end else None,
            },
            "channel": plan.channel,
        }
    finally:
        conn.close()
