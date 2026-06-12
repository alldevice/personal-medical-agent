from pathlib import Path

from hermes_medical_agent.storage import MedicalStore
from hermes_medical_agent.telegram_cache_ingest import (
    ingest_cache_dirs,
    resolve_telegram_reply_config,
)


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

def test_telegram_reply_config_uses_single_allowed_user_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_MEDICAL_TELEGRAM_REPLY_ENABLED", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "123456")

    config = resolve_telegram_reply_config()

    assert config is not None
    assert config.bot_token == "test-token"
    assert config.chat_id == "123456"


def test_telegram_reply_config_requires_unambiguous_chat(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_MEDICAL_TELEGRAM_REPLY_ENABLED", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "123,456")

    assert resolve_telegram_reply_config() is None

    monkeypatch.setenv("HERMES_MEDICAL_TELEGRAM_REPLY_CHAT_ID", "789")
    config = resolve_telegram_reply_config()

    assert config is not None
    assert config.chat_id == "789"


def test_ingest_sends_reply_for_new_file_only(tmp_path: Path, monkeypatch) -> None:
    store = make_store(tmp_path)
    cache = tmp_path / "cache" / "images"
    cache.mkdir(parents=True)
    source = cache / "photo.jpg"
    source.write_bytes(b"fake jpg bytes")

    sent: list[tuple[str, str]] = []

    def fake_send(config, text):
        sent.append((config.chat_id, text))

    monkeypatch.setenv("HERMES_MEDICAL_TELEGRAM_REPLY_ENABLED", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "123456")
    monkeypatch.setattr(
        "hermes_medical_agent.telegram_cache_ingest.send_telegram_message",
        fake_send,
    )

    first = ingest_cache_dirs(store, [cache])
    assert first[0].status.startswith("ingested")
    assert len(sent) == 1
    assert sent[0][0] == "123456"
    assert "✅ Документ импортирован" in sent[0][1]
    assert str(first[0].document_id) in sent[0][1]
    assert "sha:" in sent[0][1]

    sent.clear()
    second = ingest_cache_dirs(store, [cache])
    assert second[0].status == "already_recorded"
    assert sent == []

