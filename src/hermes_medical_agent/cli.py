from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from hermes_medical_agent.parser import parse_caption
from hermes_medical_agent.settings import load_settings
from hermes_medical_agent.storage import MedicalStore
from hermes_medical_agent.search_index import (
    extract_text_for_document,
    rebuild_search_index,
    search_documents,
)


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

    extract = sub.add_parser(
        "extract",
        help="Materialize fast-access files under data/extracted while keeping raw originals",
    )
    extract.add_argument("--id", dest="document_id", default=None, help="Extract one document id")
    extract.add_argument("--all", action="store_true", help="Extract all stored documents")

    index = sub.add_parser("index", help="Extract text and rebuild SQLite FTS search index")
    index.add_argument("--id", dest="document_id", default=None, help="Index one document id")
    index.add_argument("--all", action="store_true", help="Extract/index all stored documents")
    index.add_argument("--rebuild", action="store_true", help="Only rebuild FTS from existing extracted text")

    search = sub.add_parser("search", help="Search extracted text and timeline notes")
    search.add_argument("query", help="Search query")
    search.add_argument("--limit", type=int, default=10)

    summary = sub.add_parser("summary", help="Source-linked search summary for a topic")
    summary.add_argument("topic", help="Topic to summarize from stored sources")
    summary.add_argument("--limit", type=int, default=10)

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
    manifest = store.extract_document(stored.document_id)

    print("stored medical document")
    print(f"id={stored.document_id}")
    print(f"type={document_type or 'unknown'}")
    print(f"date={document_date or 'unknown'}")
    print(f"sha256={stored.sha256}")
    print(f"path={stored.stored_path}")
    print(f"extracted_dir={manifest['extracted_dir']}")
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


def cmd_extract(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()

    if not args.all and not args.document_id:
        raise SystemExit("use --all or --id <document_id>")
    if args.all and args.document_id:
        raise SystemExit("use either --all or --id, not both")

    documents = store.list_documents() if args.all else [store.get_document(args.document_id)]
    print(f"extracting documents={len(documents)} into {store.extracted_dir}")
    for row in documents:
        manifest = store.extract_document(str(row["id"]))
        written_files = manifest["written_files"]
        skipped_files = manifest["skipped_existing_files"]
        assert isinstance(written_files, list)
        assert isinstance(skipped_files, list)
        print(
            f"id={manifest['document_id']} "
            f"written={len(written_files)} "
            f"skipped={len(skipped_files)} "
            f"dir={manifest['extracted_dir']}"
        )
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()

    if args.rebuild:
        count = rebuild_search_index(store)
        print(f"rebuilt search index entries={count}")
        return 0

    if not args.all and not args.document_id:
        raise SystemExit("use --all, --id <document_id>, or --rebuild")
    if args.all and args.document_id:
        raise SystemExit("use either --all or --id, not both")

    documents = store.list_documents() if args.all else [store.get_document(args.document_id)]
    print(f"indexing documents={len(documents)}")
    for row in documents:
        result = extract_text_for_document(store, str(row["id"]), update_index=False)
        print(
            f"id={result.document_id} "
            f"chars={result.characters} "
            f"method={result.extraction_method} "
            f"quality={result.quality_flag} "
            f"text={result.extracted_text_path}"
        )
        if result.error:
            print(f"warning={result.error}")

    count = rebuild_search_index(store)
    print(f"rebuilt search index entries={count}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()

    rows = search_documents(store, args.query, limit=args.limit)
    if not rows:
        print("no search results")
        return 0

    for row in rows:
        document_id = row.get("document_id") or "no-document"
        scope = row.get("scope") or "unknown"
        title = row.get("title") or "Untitled"
        date = row.get("document_date") or "date unknown"
        snippet = row.get("snippet") or ""
        sha = (row.get("sha256") or "")[:12]
        print(f"- id={document_id} scope={scope} date={date} sha={sha}")
        print(f"  title={title}")
        print(f"  snippet={snippet}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()

    rows = search_documents(store, args.topic, limit=args.limit)
    if not rows:
        print("no source-linked material found for this topic")
        return 0

    print("Source-linked material only. Interpretations must stay separate from document facts.")
    for index, row in enumerate(rows, start=1):
        document_id = row.get("document_id") or "no-document"
        scope = row.get("scope") or "unknown"
        title = row.get("title") or "Untitled"
        date = row.get("document_date") or "date unknown"
        snippet = row.get("snippet") or ""
        print(f"{index}. {title}")
        print(f"   id={document_id} scope={scope} date={date}")
        print(f"   source excerpt={snippet}")
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
    if args.command == "extract":
        return cmd_extract(args)
    if args.command == "index":
        return cmd_index(args)
    if args.command == "search":
        return cmd_search(args)
    if args.command == "summary":
        return cmd_summary(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
