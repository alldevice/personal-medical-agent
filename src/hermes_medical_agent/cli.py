from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from hermes_medical_agent.parser import parse_caption
from hermes_medical_agent.settings import load_settings
from hermes_medical_agent.storage import MedicalStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medical-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create vault directories and initialize SQLite schema")

    ingest = sub.add_parser("ingest", help="Store one source file and add a timeline item")
    ingest.add_argument("--file", required=True, type=Path, help="Path to source PDF/image/file")
    ingest.add_argument("--caption", default=None, help="Free caption or type/date/comment lines")
    ingest.add_argument("--caption-file", type=Path, default=None, help="File containing caption text")
    ingest.add_argument("--type", dest="document_type", default=None, help="Document type")
    ingest.add_argument("--date", dest="document_date", default=None, help="Document date, e.g. 2026-06-10")
    ingest.add_argument("--comment", default=None, help="User comment")
    ingest.add_argument("--source-user", type=int, default=0, help="Telegram/Hermes source user id")
    ingest.add_argument("--source-message", type=int, default=0, help="Telegram/Hermes source message id")

    timeline = sub.add_parser("timeline", help="Print recent timeline items")
    timeline.add_argument("--limit", type=int, default=20)

    return parser


def read_caption(args: argparse.Namespace) -> str | None:
    if args.caption_file:
        return args.caption_file.read_text(encoding="utf-8")
    return args.caption


def cmd_init() -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()
    print(f"initialized data_dir={settings.medical_data_dir}")
    print(f"initialized db={settings.medical_db_path}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()

    source = args.file.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"source file not found: {source}")

    caption_meta = parse_caption(read_caption(args))
    document_type = args.document_type or caption_meta.document_type
    document_date = args.document_date or caption_meta.document_date
    comment = args.comment or caption_meta.comment
    mime_type = mimetypes.guess_type(source.name)[0]

    content = source.read_bytes()
    stored = store.store_bytes(content, source.name)
    store.insert_document(
        document=stored,
        telegram_user_id=args.source_user,
        telegram_message_id=args.source_message,
        original_filename=source.name,
        mime_type=mime_type,
        document_type=document_type,
        document_date=document_date,
        user_comment=comment,
    )

    print("stored medical document")
    print(f"id={stored.document_id}")
    print(f"type={document_type or 'unknown'}")
    print(f"date={document_date or 'unknown'}")
    print(f"sha256={stored.sha256}")
    print(f"path={stored.stored_path}")
    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()
    rows = store.recent_timeline(limit=args.limit)
    if not rows:
        print("timeline is empty")
        return 0
    for date, title, body in rows:
        print(f"- {date or 'date unknown'} — {title}: {body}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        return cmd_init()
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "timeline":
        return cmd_timeline(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
