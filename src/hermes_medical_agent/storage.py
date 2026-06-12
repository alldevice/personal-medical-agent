from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
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
        self.extracted_dir = data_dir / "extracted"
        self.extracted_text_dir = data_dir / "extracted_text"
        self.normalized_dir = data_dir / "normalized"
        self.timeline_dir = data_dir / "timeline"

    def init(self) -> None:
        for path in [
            self.raw_dir,
            self.extracted_dir,
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

    def list_documents(self) -> list[dict[str, str | None]]:
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                """
                SELECT id, original_filename, stored_path, sha256, mime_type,
                       document_type, document_date, user_comment, processing_status
                FROM documents
                ORDER BY received_at ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, document_id: str) -> dict[str, str | None]:
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                """
                SELECT id, original_filename, stored_path, sha256, mime_type,
                       document_type, document_date, user_comment, processing_status
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"document not found: {document_id}")
        return dict(row)

    def extract_document(self, document_id: str) -> dict[str, object]:
        """Materialize a fast-access copy under data/extracted/<document_id>.

        The original stored_path remains the immutable source of truth in data/raw.
        ZIP files are unpacked once; non-ZIP originals are copied once into the
        extracted directory so later text/OCR/indexing jobs can work from a stable
        per-document folder without touching the Telegram cache.
        """

        row = self.get_document(document_id)
        source = Path(str(row["stored_path"]))
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"stored source missing: {source}")

        target_dir = self.extracted_dir / document_id
        target_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        skipped: list[str] = []
        files_dir = target_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as archive:
                for index, info in enumerate(archive.infolist(), start=1):
                    if info.is_dir():
                        continue
                    original_name = info.filename
                    relative = Path(original_name)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError(f"unsafe ZIP member path: {original_name}")
                    filename = self._extracted_filename(index, original_name)
                    destination = files_dir / filename
                    if destination.exists():
                        skipped.append(original_name)
                        continue
                    with archive.open(info) as src, destination.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    written.append(original_name)
        else:
            filename = self._extracted_filename(1, source.name)
            destination = files_dir / filename
            if destination.exists():
                skipped.append(source.name)
            else:
                shutil.copy2(source, destination)
                written.append(source.name)

        manifest = {
            "document_id": document_id,
            "original_filename": row.get("original_filename"),
            "stored_path": str(source),
            "sha256": row.get("sha256"),
            "extracted_dir": str(target_dir),
            "written_files": written,
            "skipped_existing_files": skipped,
            "updated_at": utc_now(),
        }
        (target_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "UPDATE documents SET processing_status = ? WHERE id = ?",
                ("stored+extracted", document_id),
            )
        return manifest

    @staticmethod
    def _extracted_filename(index: int, original_name: str) -> str:
        """Return a stable, short filename for materialized archive members."""

        name = Path(original_name).name or f"file-{index}"
        stem = Path(name).stem or "file"
        suffix = Path(name).suffix[:20]
        cleaned = "".join(ch if ch not in '/\\\0' else "_" for ch in stem).strip()
        cleaned = " ".join(cleaned.split()) or "file"
        max_stem = 96
        if len(cleaned) > max_stem:
            digest = hashlib.sha256(original_name.encode("utf-8", errors="ignore")).hexdigest()[:10]
            cleaned = f"{cleaned[: max_stem - 11]}_{digest}"
        candidate = f"{index:04d}_{cleaned}{suffix}"
        if len(candidate.encode("utf-8", errors="ignore")) > 180:
            digest = hashlib.sha256(original_name.encode("utf-8", errors="ignore")).hexdigest()[:16]
            candidate = f"{index:04d}_{digest}{suffix}"
        return candidate

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
