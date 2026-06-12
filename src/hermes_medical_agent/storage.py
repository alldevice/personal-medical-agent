from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class StoredDocument:
    document_id: str
    stored_path: Path
    sha256: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    telegram_user_id INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    original_filename TEXT,
    stored_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    mime_type TEXT,
    document_type TEXT,
    document_date TEXT,
    user_comment TEXT,
    received_at TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    extracted_text_path TEXT,
    summary TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS timeline_items (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    event_date TEXT,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source_quote TEXT,
    confidence REAL,
    verified_by_user INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(document_date);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_timeline_date ON timeline_items(event_date);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MedicalStore:
    def __init__(self, data_dir: Path, db_path: Path) -> None:
        self.data_dir = data_dir
        self.db_path = db_path
        self.raw_dir = data_dir / "raw"
        self.extracted_text_dir = data_dir / "extracted_text"
        self.normalized_dir = data_dir / "normalized"
        self.timeline_dir = data_dir / "timeline"

    def init(self) -> None:
        for path in [
            self.raw_dir,
            self.extracted_text_dir,
            self.normalized_dir,
            self.timeline_dir,
            self.db_path.parent,
            self.data_dir / "audit",
            self.data_dir / "backups",
        ]:
            path.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as con:
            con.executescript(SCHEMA)

    def store_bytes(self, content: bytes, filename: str | None) -> StoredDocument:
        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        document_id = str(uuid4())
        safe_name = filename or "telegram_file.bin"
        safe_name = safe_name.replace("/", "_").replace("\\", "_")
        target_dir = self.raw_dir / today
        target_dir.mkdir(parents=True, exist_ok=True)
        stored_path = target_dir / f"{document_id}_{safe_name}"
        stored_path.write_bytes(content)
        sha256 = hashlib.sha256(content).hexdigest()
        return StoredDocument(document_id=document_id, stored_path=stored_path, sha256=sha256)

    def insert_document(
        self,
        *,
        document: StoredDocument,
        telegram_user_id: int,
        telegram_message_id: int,
        original_filename: str | None,
        mime_type: str | None,
        document_type: str | None,
        document_date: str | None,
        user_comment: str | None,
    ) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """
                INSERT INTO documents (
                    id, telegram_user_id, telegram_message_id, original_filename,
                    stored_path, sha256, mime_type, document_type, document_date,
                    user_comment, received_at, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    telegram_user_id,
                    telegram_message_id,
                    original_filename,
                    str(document.stored_path),
                    document.sha256,
                    mime_type,
                    document_type,
                    document_date,
                    user_comment,
                    utc_now(),
                    "stored",
                ),
            )
            title = document_type or "Medical document"
            body = user_comment or "Document received via Telegram."
            con.execute(
                """
                INSERT INTO timeline_items (
                    id, document_id, event_date, event_type, title, body, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    document.document_id,
                    document_date,
                    "document_received",
                    title,
                    body,
                    0.5,
                    utc_now(),
                ),
            )

    def recent_timeline(self, limit: int = 20) -> list[tuple[str | None, str, str]]:
        with sqlite3.connect(self.db_path) as con:
            rows = con.execute(
                """
                SELECT event_date, title, body
                FROM timeline_items
                ORDER BY COALESCE(event_date, created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [(row[0], row[1], row[2]) for row in rows]
