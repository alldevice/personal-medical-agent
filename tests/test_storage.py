import sqlite3
from pathlib import Path

from hermes_medical_agent.storage import MedicalStore


def make_store(tmp_path: Path) -> MedicalStore:
    store = MedicalStore(tmp_path / "data", tmp_path / "data" / "db" / "medical.sqlite")
    store.init()
    return store


def test_store_bytes_reuses_existing_document_for_same_sha(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    content = b"same image bytes"

    first = store.store_bytes(content, "image.jpg")
    store.insert_document(
        document=first,
        telegram_user_id=0,
        telegram_message_id=0,
        original_filename="image.jpg",
        mime_type="image/jpeg",
        document_type="Telegram image attachment",
        document_date="2026-06-12",
        user_comment="first ingest",
    )

    second = store.store_bytes(content, "image.jpg")
    store.insert_document(
        document=second,
        telegram_user_id=0,
        telegram_message_id=0,
        original_filename="image.jpg",
        mime_type="image/jpeg",
        document_type="annotated image",
        document_date="2026-06-12",
        user_comment="second ingest metadata only",
    )

    assert second.document_id == first.document_id
    assert second.stored_path == first.stored_path

    with sqlite3.connect(store.db_path) as con:
        document_count = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        timeline_rows = con.execute(
            "SELECT event_type, title, body FROM timeline_items ORDER BY created_at ASC"
        ).fetchall()

    assert document_count == 1
    assert len(timeline_rows) == 2
    assert timeline_rows[0][0] == "document_received"
    assert timeline_rows[1][0] == "duplicate_document_received"
    assert timeline_rows[1][1] == "annotated image"
    assert timeline_rows[1][2] == "second ingest metadata only"


def test_init_adds_document_role_columns_to_existing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "db" / "medical.sqlite"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE documents (
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
            )
            """
        )

    store = MedicalStore(tmp_path / "data", db_path)
    store.init()

    with sqlite3.connect(db_path) as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(documents)")}

    assert "document_role" in columns
    assert "role_note" in columns
