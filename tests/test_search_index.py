from pathlib import Path

from hermes_medical_agent.search_index import (
    extract_text_for_document,
    rebuild_search_index,
    search_documents,
)
from hermes_medical_agent.storage import MedicalStore


def make_store(tmp_path: Path) -> MedicalStore:
    data_dir = tmp_path / "data"
    store = MedicalStore(data_dir, data_dir / "db" / "medical.sqlite")
    store.init()
    return store


def test_extract_plain_text_and_search(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    stored = store.store_bytes(
        "Gastroscopy report: duodenum erosion noted.".encode("utf-8"),
        "report.txt",
    )
    store.insert_document(
        document=stored,
        telegram_user_id=237187787,
        telegram_message_id=1,
        original_filename="report.txt",
        mime_type="text/plain",
        document_type="consultation",
        document_date="2026-06-12",
        user_comment="GI visit",
    )

    result = extract_text_for_document(store, stored.document_id)
    extracted = Path(result.extracted_text_path).read_text(encoding="utf-8")

    assert result.quality_flag == "text"
    assert "duodenum erosion" in extracted

    hits = search_documents(store, "duodenum erosion", limit=5)

    assert hits
    assert hits[0]["document_id"] == stored.document_id
    assert hits[0]["scope"] == "document_text"


def test_rebuild_index_includes_timeline_notes(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    stored = store.store_bytes(b"minimal source", "note.txt")
    store.insert_document(
        document=stored,
        telegram_user_id=237187787,
        telegram_message_id=2,
        original_filename="note.txt",
        mime_type="text/plain",
        document_type="symptom",
        document_date="2026-06-11",
        user_comment="night stomach pain after NSAID",
    )

    count = rebuild_search_index(store)
    hits = search_documents(store, "stomach pain", limit=5)

    assert count >= 1
    assert hits
    assert any(hit["scope"] == "timeline_note" for hit in hits)
