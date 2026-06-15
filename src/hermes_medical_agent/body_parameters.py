from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from hermes_medical_agent.storage import MedicalStore, utc_now


BODY_PARAMETER_SCHEMA = """
CREATE TABLE IF NOT EXISTS body_parameters (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    timeline_item_id TEXT,
    observed_at TEXT NOT NULL,
    parameter_group TEXT,
    parameter_name TEXT NOT NULL,
    parameter_code TEXT,
    value_text TEXT,
    value_numeric REAL,
    unit TEXT,
    reference_range TEXT,
    note TEXT,
    body_site TEXT,
    method TEXT,
    source_quote TEXT,
    confidence REAL,
    verified_by_user INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id),
    FOREIGN KEY(timeline_item_id) REFERENCES timeline_items(id)
);

CREATE INDEX IF NOT EXISTS idx_body_parameters_observed_at ON body_parameters(observed_at);
CREATE INDEX IF NOT EXISTS idx_body_parameters_name ON body_parameters(parameter_name);
CREATE INDEX IF NOT EXISTS idx_body_parameters_group ON body_parameters(parameter_group);
CREATE INDEX IF NOT EXISTS idx_body_parameters_document ON body_parameters(document_id);
CREATE INDEX IF NOT EXISTS idx_body_parameters_timeline ON body_parameters(timeline_item_id);
"""


def ensure_body_parameter_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as con:
        con.executescript(BODY_PARAMETER_SCHEMA)


def add_body_parameter(
    store: MedicalStore,
    *,
    observed_at: str,
    parameter_name: str,
    document_id: str | None = None,
    timeline_item_id: str | None = None,
    parameter_group: str | None = None,
    parameter_code: str | None = None,
    value_text: str | None = None,
    value_numeric: float | None = None,
    unit: str | None = None,
    reference_range: str | None = None,
    note: str | None = None,
    body_site: str | None = None,
    method: str | None = None,
    source_quote: str | None = None,
    confidence: float | None = 0.5,
    verified_by_user: int = 0,
) -> str:
    if not observed_at.strip():
        raise ValueError("observed_at is required")
    if not parameter_name.strip():
        raise ValueError("parameter_name is required")
    if value_text is None and value_numeric is None and not note:
        raise ValueError("provide value_text, value_numeric, or note")

    ensure_body_parameter_schema(store.db_path)

    if document_id is not None:
        store.get_document(document_id)

    parameter_id = str(uuid4())
    with sqlite3.connect(store.db_path) as con:
        if timeline_item_id is not None:
            exists = con.execute(
                "SELECT 1 FROM timeline_items WHERE id = ?",
                (timeline_item_id,),
            ).fetchone()
            if exists is None:
                raise KeyError(f"timeline item not found: {timeline_item_id}")

        con.execute(
            """
            INSERT INTO body_parameters (
                id, document_id, timeline_item_id, observed_at, parameter_group,
                parameter_name, parameter_code, value_text, value_numeric, unit,
                reference_range, note, body_site, method, source_quote,
                confidence, verified_by_user, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parameter_id,
                document_id,
                timeline_item_id,
                observed_at,
                parameter_group,
                parameter_name,
                parameter_code,
                value_text,
                value_numeric,
                unit,
                reference_range,
                note,
                body_site,
                method,
                source_quote,
                confidence,
                verified_by_user,
                utc_now(),
            ),
        )
    return parameter_id


def list_body_parameters(store: MedicalStore, *, limit: int = 50) -> list[dict[str, Any]]:
    ensure_body_parameter_schema(store.db_path)
    with sqlite3.connect(store.db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT id, document_id, timeline_item_id, observed_at,
                   parameter_group, parameter_name, parameter_code, value_text,
                   value_numeric, unit, reference_range, note, body_site,
                   method, source_quote, confidence, verified_by_user, created_at
            FROM body_parameters
            ORDER BY observed_at DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def search_body_parameters(
    store: MedicalStore,
    query: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_body_parameter_schema(store.db_path)
    tokens = [token for token in query.casefold().split() if token.strip()]
    if not tokens:
        return list_body_parameters(store, limit=limit)

    clauses: list[str] = []
    values: list[str | int] = []
    fields = [
        "observed_at",
        "parameter_group",
        "parameter_name",
        "parameter_code",
        "value_text",
        "unit",
        "reference_range",
        "note",
        "body_site",
        "method",
        "source_quote",
    ]
    for token in tokens:
        like = f"%{token}%"
        clauses.append("(" + " OR ".join(f"lower(COALESCE({field}, '')) LIKE ?" for field in fields) + ")")
        values.extend([like] * len(fields))

    sql = f"""
        SELECT id, document_id, timeline_item_id, observed_at,
               parameter_group, parameter_name, parameter_code, value_text,
               value_numeric, unit, reference_range, note, body_site,
               method, source_quote, confidence, verified_by_user, created_at
        FROM body_parameters
        WHERE {' AND '.join(clauses)}
        ORDER BY observed_at DESC, created_at DESC
        LIMIT ?
    """
    values.append(limit)

    with sqlite3.connect(store.db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, values).fetchall()
    return [dict(row) for row in rows]


def body_parameter_to_search_text(row: sqlite3.Row | dict[str, Any]) -> tuple[str, str]:
    get = row.get if isinstance(row, dict) else row.__getitem__
    value = get("value_text") or ""
    numeric = get("value_numeric")
    if numeric is not None:
        value = f"{numeric:g} {get('unit') or ''}".strip()
    title = " — ".join(
        part
        for part in [
            get("parameter_name") or "body parameter",
            value,
            get("note") or "",
        ]
        if str(part).strip()
    )
    body = "\n".join(
        part
        for part in [
            f"observed_at: {get('observed_at')}" if get("observed_at") else "",
            f"parameter_group: {get('parameter_group')}" if get("parameter_group") else "",
            f"parameter_code: {get('parameter_code')}" if get("parameter_code") else "",
            f"value: {value}" if value else "",
            f"unit: {get('unit')}" if get("unit") else "",
            f"reference_range: {get('reference_range')}" if get("reference_range") else "",
            f"note: {get('note')}" if get("note") else "",
            f"body_site: {get('body_site')}" if get("body_site") else "",
            f"method: {get('method')}" if get("method") else "",
            get("source_quote") or "",
        ]
        if part
    )
    return title, body
