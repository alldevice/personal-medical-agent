from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_medical_agent.body_parameters import ensure_body_parameter_schema, body_parameter_to_search_text
from hermes_medical_agent.storage import MedicalStore, utc_now


SEARCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS extracted_texts (
    document_id TEXT PRIMARY KEY,
    extracted_text_path TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    quality_flag TEXT NOT NULL,
    error TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS medical_search_fts USING fts5(
    document_id UNINDEXED,
    scope UNINDEXED,
    title,
    body,
    text,
    tokenize='unicode61'
);
"""

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


@dataclass(frozen=True)
class ExtractedTextResult:
    document_id: str
    extracted_text_path: str
    extraction_method: str
    quality_flag: str
    error: str | None
    characters: int


def ensure_search_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as con:
        con.executescript(SEARCH_SCHEMA)
    ensure_body_parameter_schema(db_path)


def extract_text_for_document(
    store: MedicalStore,
    document_id: str,
    *,
    update_index: bool = True,
) -> ExtractedTextResult:
    """Extract searchable text without changing the raw source-of-truth document.

    The raw file remains under data/raw. This reads the stable working copy under
    data/extracted/<document_id>/files and writes text to data/extracted_text.
    Extraction failures are recorded and do not block storing or indexing metadata.
    """

    ensure_search_schema(store.db_path)

    manifest = store.extract_document(document_id)
    extracted_dir = Path(str(manifest["extracted_dir"]))
    files_dir = extracted_dir / "files"
    text_dir = store.extracted_text_dir
    text_dir.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    methods: set[str] = set()
    errors: list[str] = []

    for path in sorted(files_dir.iterdir() if files_dir.exists() else []):
        if not path.is_file():
            continue

        try:
            text, method, warning = _extract_text_from_path(path)
        except Exception as exc:  # extraction must never break raw ingest
            text = ""
            method = "failed"
            warning = f"{type(exc).__name__}: {exc}"

        methods.add(method)

        if warning:
            errors.append(f"{path.name}: {warning}")

        if text.strip():
            sections.append(f"# {path.name}\n\n{text.strip()}")

    combined_text = "\n\n".join(sections).strip()
    error_text = "\n".join(errors) if errors else None

    if not combined_text and error_text:
        combined_text = "\n".join(f"[extraction note] {line}" for line in errors)

    extraction_method = "+".join(sorted(methods)) if methods else "none"
    quality_flag = _quality_flag(combined_text, methods, errors)

    extracted_text_path = text_dir / f"{document_id}.txt"
    extracted_text_path.write_text(combined_text, encoding="utf-8")

    with sqlite3.connect(store.db_path) as con:
        con.execute(
            """
            INSERT INTO extracted_texts (
                document_id, extracted_text_path, extraction_method,
                quality_flag, error, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                extracted_text_path = excluded.extracted_text_path,
                extraction_method = excluded.extraction_method,
                quality_flag = excluded.quality_flag,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (
                document_id,
                str(extracted_text_path),
                extraction_method,
                quality_flag,
                error_text,
                utc_now(),
            ),
        )
        con.execute(
            """
            UPDATE documents
            SET extracted_text_path = ?,
                processing_status = ?
            WHERE id = ?
            """,
            (str(extracted_text_path), f"stored+extracted+text:{quality_flag}", document_id),
        )

    result = ExtractedTextResult(
        document_id=document_id,
        extracted_text_path=str(extracted_text_path),
        extraction_method=extraction_method,
        quality_flag=quality_flag,
        error=error_text,
        characters=len(combined_text),
    )

    if update_index:
        rebuild_search_index(store)

    return result


def rebuild_search_index(store: MedicalStore) -> int:
    """Rebuild the SQLite FTS index from extracted text, timeline notes, and body parameters."""

    ensure_search_schema(store.db_path)

    indexed = 0
    with sqlite3.connect(store.db_path) as con:
        con.row_factory = sqlite3.Row
        con.execute("DELETE FROM medical_search_fts")

        documents = con.execute(
            """
            SELECT d.id, d.original_filename, d.document_type, d.document_date,
                   d.user_comment, d.sha256, et.extracted_text_path
            FROM documents d
            LEFT JOIN extracted_texts et ON et.document_id = d.id
            ORDER BY COALESCE(d.document_date, d.received_at) ASC
            """
        ).fetchall()

        for row in documents:
            text = _read_optional_text(row["extracted_text_path"])
            title = row["document_type"] or row["original_filename"] or "Medical document"
            body_parts = [
                f"date: {row['document_date']}" if row["document_date"] else "",
                f"comment: {row['user_comment']}" if row["user_comment"] else "",
                f"sha256: {row['sha256'][:12]}" if row["sha256"] else "",
            ]
            body = "\n".join(part for part in body_parts if part)

            if text.strip() or body.strip() or title.strip():
                con.execute(
                    """
                    INSERT INTO medical_search_fts(document_id, scope, title, body, text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (row["id"], "document_text", title, body, text),
                )
                indexed += 1

        timeline = con.execute(
            """
            SELECT document_id, event_type, event_date, title, body, source_quote
            FROM timeline_items
            ORDER BY COALESCE(event_date, created_at) ASC
            """
        ).fetchall()

        for row in timeline:
            document_id = row["document_id"] or ""
            title = row["title"] or row["event_type"] or "Timeline item"
            body = "\n".join(
                part
                for part in [
                    f"event_type: {row['event_type']}" if row["event_type"] else "",
                    f"event_date: {row['event_date']}" if row["event_date"] else "",
                    row["body"] or "",
                    row["source_quote"] or "",
                ]
                if part
            )
            con.execute(
                """
                INSERT INTO medical_search_fts(document_id, scope, title, body, text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document_id, "timeline_note", title, body, ""),
            )
            indexed += 1

        body_parameters = con.execute(
            """
            SELECT id, document_id, timeline_item_id, observed_at,
                   parameter_group, parameter_name, parameter_code, value_text,
                   value_numeric, unit, reference_range, note, body_site,
                   method, source_quote, confidence, verified_by_user, created_at
            FROM body_parameters
            ORDER BY observed_at ASC, created_at ASC
            """
        ).fetchall()

        for row in body_parameters:
            title, body = body_parameter_to_search_text(row)
            con.execute(
                """
                INSERT INTO medical_search_fts(document_id, scope, title, body, text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row["document_id"] or "", "body_parameter", title, body, ""),
            )
            indexed += 1

    return indexed


def search_documents(store: MedicalStore, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    ensure_search_schema(store.db_path)
    fts_query = _make_fts_query(query)
    if not fts_query:
        return []

    with sqlite3.connect(store.db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT
                medical_search_fts.document_id,
                medical_search_fts.scope,
                medical_search_fts.title,
                medical_search_fts.body,
                snippet(medical_search_fts, 4, '[', ']', '…', 18) AS snippet,
                d.original_filename,
                d.document_type,
                d.document_date,
                d.sha256
            FROM medical_search_fts
            LEFT JOIN documents d ON d.id = medical_search_fts.document_id
            WHERE medical_search_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def _extract_text_from_path(path: Path) -> tuple[str, str, str | None]:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_text(path), "pdf-text", None

    if suffix in IMAGE_SUFFIXES:
        return _extract_image_text(path), "ocr", None

    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace"), "plain-text", None

    return "", "unsupported", f"unsupported file type: {suffix or 'no suffix'}"


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[page {index}]\n{text.strip()}")
    return "\n\n".join(pages)


def _extract_image_text(path: Path) -> str:
    from PIL import Image
    import pytesseract

    with Image.open(path) as image:
        try:
            return pytesseract.image_to_string(image, lang="rus+eng")
        except Exception:
            return pytesseract.image_to_string(image)


def _quality_flag(text: str, methods: set[str], errors: list[str]) -> str:
    has_text = bool(text.strip())
    if not has_text and errors:
        return "failed"
    if not has_text:
        return "empty"
    if errors:
        return "partial"
    if "ocr" in methods:
        return "ocr"
    return "text"


def _read_optional_text(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _make_fts_query(query: str) -> str:
    # Build a conservative AND query from words. SQLite FTS5 accepts bare
    # sanitized prefix terms like "эрози*" and "гастр*". Avoid parenthesized
    # OR groups here because some SQLite/FTS builds reject that syntax.
    tokens = re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", query.casefold())
    tokens = [token[:64] for token in tokens if token.strip()]
    if not tokens:
        return ""

    terms: list[str] = []
    for token in tokens[:16]:
        if len(token) >= 7:
            stem = token[:-2]
        elif len(token) >= 5:
            stem = token[:-1]
        else:
            stem = token
        terms.append(f"{_fts_term(stem)}*")

    return " ".join(terms)


def _fts_term(token: str) -> str:
    # Tokens come from a strict alphanumeric/Cyrillic regex, so they can be used
    # as bare FTS5 terms. Keep this helper separate to make future escaping rules
    # explicit if query syntax expands.
    return token
