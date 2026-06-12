from pathlib import Path

from hermes_medical_agent.storage import MedicalStore
from hermes_medical_agent.telegram_cache_ingest import ingest_cache_dirs


def make_store(tmp_path: Path) -> MedicalStore:
    store = MedicalStore(tmp_path / "data", tmp_path / "data" / "db" / "medical.sqlite")
    store.init()
    return store


def test_ingest_cache_file_once_and_skip_duplicate(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    cache = tmp_path / "cache" / "documents"
    cache.mkdir(parents=True)
    source = cache / "gastroscopy.txt"
    source.write_text("Эрозии желудка после гастроскопии.", encoding="utf-8")

    first = ingest_cache_dirs(store, [cache])
    second = ingest_cache_dirs(store, [cache])

    assert len(first) == 1
    assert first[0].status.startswith("ingested")
    assert first[0].document_id

    assert len(second) == 1
    assert second[0].status == "already_recorded"
    assert second[0].document_id == first[0].document_id


def test_dry_run_does_not_ingest(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    cache = tmp_path / "cache" / "documents"
    cache.mkdir(parents=True)
    (cache / "report.pdf").write_bytes(b"%PDF-1.4\n")

    results = ingest_cache_dirs(store, [cache], dry_run=True)

    assert len(results) == 1
    assert results[0].status == "would_ingest"
    assert results[0].document_id is None
    assert store.list_documents() == []


def test_dry_run_existing_cache_path_reports_already_recorded(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    cache = tmp_path / "cache" / "documents"
    cache.mkdir(parents=True)
    source = cache / "gastroscopy.txt"
    source.write_text("Эрозии желудка после гастроскопии.", encoding="utf-8")

    first = ingest_cache_dirs(store, [cache])
    dry_run = ingest_cache_dirs(store, [cache], dry_run=True)

    assert len(dry_run) == 1
    assert dry_run[0].status == "already_recorded"
    assert dry_run[0].document_id == first[0].document_id


def test_duplicate_scan_does_not_rebuild_index(tmp_path: Path, monkeypatch) -> None:
    store = make_store(tmp_path)
    cache = tmp_path / "cache" / "documents"
    cache.mkdir(parents=True)
    source = cache / "gastroscopy.txt"
    source.write_text("Эрозии желудка после гастроскопии.", encoding="utf-8")

    calls = 0

    def fake_rebuild_search_index(_store: MedicalStore) -> int:
        nonlocal calls
        calls += 1
        return 1

    monkeypatch.setattr(
        "hermes_medical_agent.telegram_cache_ingest.rebuild_search_index",
        fake_rebuild_search_index,
    )

    first = ingest_cache_dirs(store, [cache])
    second = ingest_cache_dirs(store, [cache])

    assert first[0].status.startswith("ingested")
    assert second[0].status == "already_recorded"
    assert calls == 1
