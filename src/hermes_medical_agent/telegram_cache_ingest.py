from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from hermes_medical_agent.search_index import extract_text_for_document, rebuild_search_index
from hermes_medical_agent.storage import MedicalStore

LOGGER = logging.getLogger(__name__)

TELEGRAM_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS telegram_cache_ingest (
    cache_path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    document_id TEXT,
    status TEXT NOT NULL,
    reason TEXT,
    ingested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telegram_cache_ingest_sha256
ON telegram_cache_ingest(sha256);
"""

DEFAULT_PROFILE_HOME = Path("/home/hermes/.hermes/profiles/medical_consultant")

DEFAULT_CACHE_DIRS = [
    DEFAULT_PROFILE_HOME / "cache" / "documents",
    DEFAULT_PROFILE_HOME / "document_cache",
    DEFAULT_PROFILE_HOME / "cache" / "images",
    DEFAULT_PROFILE_HOME / "image_cache",
]

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
    ".zip",
}


@dataclass(frozen=True)
class TelegramCacheIngestResult:
    path: Path
    status: str
    document_id: str | None
    sha256: str | None
    reason: str | None


@dataclass(frozen=True)
class TelegramReplyConfig:
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class TelegramReplySendResult:
    document_id: str | None
    status: str
    sent: bool
    reason: str | None = None


TRUE_ENV_VALUES = {"1", "true", "yes", "on"}


def ensure_telegram_cache_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as con:
        con.executescript(TELEGRAM_CACHE_SCHEMA)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_cache_dirs() -> list[Path]:
    return [path for path in DEFAULT_CACHE_DIRS if path.exists() and path.is_dir()]


def iter_candidate_files(cache_dirs: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in cache_dirs:
        root = root.expanduser().resolve()
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path in seen:
                continue
            seen.add(path)
            if path.name.startswith("."):
                continue
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            yield path


def resolve_telegram_reply_config(
    env: Mapping[str, str] | None = None,
) -> TelegramReplyConfig | None:
    source = os.environ if env is None else env
    enabled = source.get("HERMES_MEDICAL_TELEGRAM_REPLY_ENABLED", "").strip().lower()
    if enabled not in TRUE_ENV_VALUES:
        return None

    bot_token = source.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = (
        source.get("HERMES_MEDICAL_TELEGRAM_REPLY_CHAT_ID", "").strip()
        or source.get("TELEGRAM_NOTIFY_CHAT_ID", "").strip()
    )

    if not chat_id:
        allowed_users = [
            item.strip()
            for item in source.get("TELEGRAM_ALLOWED_USERS", "").replace(";", ",").split(",")
            if item.strip()
        ]
        if len(allowed_users) == 1 and allowed_users[0].lstrip("-").isdigit():
            chat_id = allowed_users[0]

    if not bot_token or not chat_id:
        return None

    return TelegramReplyConfig(bot_token=bot_token, chat_id=chat_id)


def send_telegram_message(
    config: TelegramReplyConfig,
    text: str,
    *,
    timeout_seconds: float = 10.0,
) -> None:
    payload = urllib.parse.urlencode(
        {
            "chat_id": config.chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{config.bot_token}/sendMessage",
        data=payload,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(f"Telegram sendMessage HTTP {response.status}: {body}")
        parsed = json.loads(body or "{}")
        if not parsed.get("ok", False):
            raise RuntimeError(f"Telegram sendMessage failed: {body}")


def should_send_telegram_reply(result: TelegramCacheIngestResult) -> bool:
    return bool(result.document_id) and (
        result.status.startswith("ingested") or result.status == "duplicate_sha"
    )


def format_telegram_reply(store: MedicalStore, result: TelegramCacheIngestResult) -> str:
    row: dict[str, str | None] = {}
    if result.document_id:
        try:
            row = store.get_document(result.document_id)
        except KeyError:
            row = {}

    if result.status.startswith("ingested"):
        header = "✅ Документ импортирован"
    elif result.status == "duplicate_sha":
        header = "ℹ️ Файл уже есть в медицинском архиве"
    else:
        header = "ℹ️ Telegram cache ingest"

    doc_type = row.get("document_type") or "unknown"
    doc_date = row.get("document_date") or "unknown"
    processing = row.get("processing_status") or result.status
    sha_prefix = (result.sha256 or row.get("sha256") or "")[:12] or "unknown"

    lines = [
        header,
        "",
        f"id: {result.document_id or 'unknown'}",
        f"type: {doc_type}",
        f"date: {doc_date}",
        f"sha: {sha_prefix}",
        f"status: {result.status}",
        f"processing: {processing}",
        f"source: {result.path.name}",
    ]
    if result.reason:
        lines.append(f"note: {result.reason}")
    return "\n".join(lines)


def send_telegram_replies_for_results(
    store: MedicalStore,
    results: Iterable[TelegramCacheIngestResult],
    *,
    config: TelegramReplyConfig | None = None,
) -> list[TelegramReplySendResult]:
    active_config = config or resolve_telegram_reply_config()
    if active_config is None:
        return []

    sent: list[TelegramReplySendResult] = []
    for result in results:
        if not should_send_telegram_reply(result):
            continue

        try:
            send_telegram_message(active_config, format_telegram_reply(store, result))
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            LOGGER.warning("telegram ingest reply failed for %s: %s", result.document_id, reason)
            sent.append(
                TelegramReplySendResult(
                    document_id=result.document_id,
                    status=result.status,
                    sent=False,
                    reason=reason,
                )
            )
        else:
            sent.append(
                TelegramReplySendResult(
                    document_id=result.document_id,
                    status=result.status,
                    sent=True,
                )
            )
    return sent


def already_recorded(store: MedicalStore, cache_path: Path, sha256: str) -> tuple[bool, str | None, str | None]:
    ensure_telegram_cache_schema(store.db_path)
    with sqlite3.connect(store.db_path) as con:
        con.row_factory = sqlite3.Row
        by_path = con.execute(
            "SELECT document_id, status, reason FROM telegram_cache_ingest WHERE cache_path = ?",
            (str(cache_path),),
        ).fetchone()
        if by_path is not None:
            return True, by_path["document_id"], "already_recorded"

        by_sha = con.execute(
            "SELECT id FROM documents WHERE sha256 = ? ORDER BY received_at ASC LIMIT 1",
            (sha256,),
        ).fetchone()
        if by_sha is not None:
            document_id = str(by_sha["id"])
            con.execute(
                """
                INSERT OR REPLACE INTO telegram_cache_ingest
                    (cache_path, sha256, document_id, status, reason, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(cache_path),
                    sha256,
                    document_id,
                    "duplicate_sha",
                    "same SHA already exists in medical vault",
                    utc_now(),
                ),
            )
            return True, document_id, "duplicate_sha"

    return False, None, None


def record_result(
    store: MedicalStore,
    *,
    cache_path: Path,
    sha256: str,
    document_id: str | None,
    status: str,
    reason: str | None,
) -> None:
    ensure_telegram_cache_schema(store.db_path)
    with sqlite3.connect(store.db_path) as con:
        con.execute(
            """
            INSERT OR REPLACE INTO telegram_cache_ingest
                (cache_path, sha256, document_id, status, reason, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(cache_path), sha256, document_id, status, reason, utc_now()),
        )


def infer_document_date(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()


def infer_document_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "Telegram PDF attachment"
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        return "Telegram image attachment"
    if suffix == ".zip":
        return "Telegram archive attachment"
    return "Telegram text/document attachment"


def ingest_cache_file(
    store: MedicalStore,
    path: Path,
    *,
    dry_run: bool = False,
    update_index: bool = True,
) -> TelegramCacheIngestResult:
    path = path.expanduser().resolve()
    sha256 = file_sha256(path)

    seen, document_id, status = already_recorded(store, path, sha256)
    if seen:
        return TelegramCacheIngestResult(
            path=path,
            status=status or "already_recorded",
            document_id=document_id,
            sha256=sha256,
            reason="already recorded or duplicate SHA",
        )

    if dry_run:
        return TelegramCacheIngestResult(
            path=path,
            status="would_ingest",
            document_id=None,
            sha256=sha256,
            reason=None,
        )

    mime_type, _ = mimetypes.guess_type(str(path))
    document = store.store_bytes(path.read_bytes(), path.name)
    store.insert_document(
        document=document,
        telegram_user_id=0,
        telegram_message_id=0,
        original_filename=path.name,
        mime_type=mime_type,
        document_type=infer_document_type(path),
        document_date=infer_document_date(path),
        user_comment=f"Imported automatically from Hermes Telegram cache: {path}",
    )

    try:
        extract_text_for_document(store, document.document_id, update_index=update_index)
        status = "ingested+indexed" if update_index else "ingested+extracted"
        reason = None
    except Exception as exc:
        status = "ingested+extract_failed"
        reason = f"{type(exc).__name__}: {exc}"

    record_result(
        store,
        cache_path=path,
        sha256=sha256,
        document_id=document.document_id,
        status=status,
        reason=reason,
    )

    return TelegramCacheIngestResult(
        path=path,
        status=status,
        document_id=document.document_id,
        sha256=sha256,
        reason=reason,
    )


def result_created_document(result: TelegramCacheIngestResult) -> bool:
    return result.status.startswith("ingested")


def ingest_cache_dirs(
    store: MedicalStore,
    cache_dirs: Iterable[Path],
    *,
    dry_run: bool = False,
    update_index: bool = True,
    rebuild_after: bool = True,
) -> list[TelegramCacheIngestResult]:
    results = [
        ingest_cache_file(store, path, dry_run=dry_run, update_index=update_index)
        for path in iter_candidate_files(cache_dirs)
    ]
    if not dry_run and rebuild_after and any(result_created_document(result) for result in results):
        rebuild_search_index(store)
    if not dry_run:
        send_telegram_replies_for_results(store, results)
    return results


def watch_cache_dirs(
    store: MedicalStore,
    cache_dirs: Iterable[Path],
    *,
    interval_seconds: float,
    once: bool,
    dry_run: bool,
) -> Iterable[list[TelegramCacheIngestResult]]:
    while True:
        yield ingest_cache_dirs(
            store,
            cache_dirs,
            dry_run=dry_run,
            update_index=True,
            rebuild_after=True,
        )
        if once:
            return
        time.sleep(interval_seconds)
