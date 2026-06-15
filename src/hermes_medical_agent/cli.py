from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from hermes_medical_agent.body_parameters import (
    add_body_parameter,
    ensure_body_parameter_schema,
    list_body_parameters,
    search_body_parameters,
)
from hermes_medical_agent.content_audit import build_content_audit_report, render_content_audit_markdown, write_content_audit_report
from hermes_medical_agent.parser import parse_caption
from hermes_medical_agent.search_index import extract_text_for_document, rebuild_search_index, search_documents
from hermes_medical_agent.settings import load_settings
from hermes_medical_agent.storage import MedicalStore
from hermes_medical_agent.telegram_cache_ingest import default_cache_dirs, watch_cache_dirs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medical-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--file", required=True, type=Path)
    ingest.add_argument("--caption", default=None)
    ingest.add_argument("--caption-file", type=Path, default=None)
    ingest.add_argument("--type", dest="document_type", default=None)
    ingest.add_argument("--date", dest="document_date", default=None)
    ingest.add_argument("--comment", default=None)
    ingest.add_argument("--source-user", type=int, default=0)
    ingest.add_argument("--source-message", type=int, default=0)

    timeline = sub.add_parser("timeline")
    timeline.add_argument("--limit", type=int, default=20)

    extract = sub.add_parser("extract")
    extract.add_argument("--id", dest="document_id", default=None)
    extract.add_argument("--all", action="store_true")

    index = sub.add_parser("index")
    index.add_argument("--id", dest="document_id", default=None)
    index.add_argument("--all", action="store_true")
    index.add_argument("--rebuild", action="store_true")

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)

    summary = sub.add_parser("summary")
    summary.add_argument("topic")
    summary.add_argument("--limit", type=int, default=10)

    audit = sub.add_parser("content-audit")
    audit.add_argument("--limit", type=int, default=100)
    audit.add_argument("--stdout", action="store_true")
    audit.add_argument("--no-write", action="store_true")

    annotate = sub.add_parser("annotate-document")
    annotate.add_argument("--id", dest="document_id", required=True)
    annotate.add_argument("--type", dest="document_type", default=None)
    annotate.add_argument("--role", dest="document_role", default=None)
    annotate.add_argument("--role-note", dest="role_note", default=None)

    add_timeline = sub.add_parser("add-timeline")
    add_timeline.add_argument("--document-id", default=None)
    add_timeline.add_argument("--date", dest="event_date", default=None)
    add_timeline.add_argument("--event-type", required=True)
    add_timeline.add_argument("--title", required=True)
    add_timeline.add_argument("--body", required=True)
    add_timeline.add_argument("--quote", dest="source_quote", default=None)
    add_timeline.add_argument("--confidence", type=float, default=0.5)
    add_timeline.add_argument("--verified", action="store_true")

    add_param = sub.add_parser("add-body-parameter")
    add_param.add_argument("--document-id", default=None)
    add_param.add_argument("--timeline-item-id", default=None)
    add_param.add_argument("--observed-at", required=True)
    add_param.add_argument("--group", dest="parameter_group", default=None)
    add_param.add_argument("--parameter", dest="parameter_name", required=True)
    add_param.add_argument("--code", dest="parameter_code", default=None)
    add_param.add_argument("--value", dest="value_text", default=None)
    add_param.add_argument("--numeric-value", type=float, default=None)
    add_param.add_argument("--unit", default=None)
    add_param.add_argument("--reference-range", default=None)
    add_param.add_argument("--note", default=None)
    add_param.add_argument("--body-site", default=None)
    add_param.add_argument("--method", default=None)
    add_param.add_argument("--quote", dest="source_quote", default=None)
    add_param.add_argument("--confidence", type=float, default=0.5)
    add_param.add_argument("--verified", action="store_true")

    body_parameters = sub.add_parser("body-parameters")
    body_parameters.add_argument("--query", default=None)
    body_parameters.add_argument("--limit", type=int, default=50)

    cache = sub.add_parser("telegram-cache-ingest")
    cache.add_argument("--cache-dir", action="append", default=[])
    cache.add_argument("--once", action="store_true")
    cache.add_argument("--dry-run", action="store_true")
    cache.add_argument("--interval", type=float, default=30.0)
    return parser


def read_caption(args: argparse.Namespace) -> str | None:
    return args.caption_file.read_text(encoding="utf-8") if args.caption_file else args.caption


def load_store() -> MedicalStore:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()
    ensure_body_parameter_schema(store.db_path)
    return store


def cmd_init() -> int:
    settings = load_settings()
    store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
    store.init()
    ensure_body_parameter_schema(store.db_path)
    print(f"initialized data_dir={settings.medical_data_dir}")
    print(f"initialized db={settings.medical_db_path}")
    print("initialized body_parameters")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    store = load_store()
    source = args.file.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"source file not found: {source}")
    caption_meta = parse_caption(read_caption(args))
    document_type = args.document_type or caption_meta.document_type
    document_date = args.document_date or caption_meta.document_date
    comment = args.comment or caption_meta.comment
    stored = store.store_bytes(source.read_bytes(), source.name)
    store.insert_document(
        document=stored,
        telegram_user_id=args.source_user,
        telegram_message_id=args.source_message,
        original_filename=source.name,
        mime_type=mimetypes.guess_type(source.name)[0],
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
    rows = load_store().recent_timeline(limit=args.limit)
    if not rows:
        print("timeline is empty")
        return 0
    for date, title, body in rows:
        print(f"- {date or 'date unknown'} — {title}: {body}")
    return 0


def selected_documents(store: MedicalStore, args: argparse.Namespace) -> list[dict[str, str | None]]:
    if not args.all and not args.document_id:
        raise SystemExit("use --all or --id <document_id>")
    if args.all and args.document_id:
        raise SystemExit("use either --all or --id, not both")
    return store.list_documents() if args.all else [store.get_document(args.document_id)]


def cmd_extract(args: argparse.Namespace) -> int:
    store = load_store()
    documents = selected_documents(store, args)
    print(f"extracting documents={len(documents)} into {store.extracted_dir}")
    for row in documents:
        manifest = store.extract_document(str(row["id"]))
        written = manifest["written_files"]
        skipped = manifest["skipped_existing_files"]
        print(
            f"id={manifest['document_id']} written={len(written)} skipped={len(skipped)} "
            f"nested_archives={len(manifest.get('nested_archives', []))} dir={manifest['extracted_dir']}"
        )
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    store = load_store()
    if args.rebuild:
        print(f"rebuilt search index entries={rebuild_search_index(store)}")
        return 0
    for row in selected_documents(store, args):
        result = extract_text_for_document(store, str(row["id"]), update_index=False)
        print(f"id={result.document_id} chars={result.characters} method={result.extraction_method} quality={result.quality_flag} text={result.extracted_text_path}")
        if result.error:
            print(f"warning={result.error}")
    print(f"rebuilt search index entries={rebuild_search_index(store)}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    rows = search_documents(load_store(), args.query, limit=args.limit)
    if not rows:
        print("no search results")
        return 0
    for row in rows:
        sha = (row.get("sha256") or "")[:12]
        print(f"- id={row.get('document_id') or 'no-document'} scope={row.get('scope') or 'unknown'} date={row.get('document_date') or 'date unknown'} sha={sha}")
        print(f"  title={row.get('title') or 'Untitled'}")
        print(f"  snippet={row.get('snippet') or ''}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    rows = search_documents(load_store(), args.topic, limit=args.limit)
    if not rows:
        print("no source-linked material found for this topic")
        return 0
    print("Source-linked material only. Interpretations must stay separate from document facts.")
    for index, row in enumerate(rows, start=1):
        print(f"{index}. {row.get('title') or 'Untitled'}")
        print(f"   id={row.get('document_id') or 'no-document'} scope={row.get('scope') or 'unknown'} date={row.get('document_date') or 'date unknown'}")
        print(f"   source excerpt={row.get('snippet') or ''}")
    return 0


def cmd_content_audit(args: argparse.Namespace) -> int:
    store = load_store()
    report = build_content_audit_report(store)
    if not args.no_write:
        print(f"audit_report={write_content_audit_report(store, report, limit=args.limit)}")
    print(f"summary total={report.total_documents} zip={report.zip_documents} manifest={report.manifest_count} extracted_text={report.extracted_text_count} needs_review={report.needs_review_count} composite_candidates={report.composite_candidate_count}")
    if args.stdout:
        print()
        print(render_content_audit_markdown(report, limit=args.limit), end="")
    return 0


def cmd_annotate_document(args: argparse.Namespace) -> int:
    if not any([args.document_type, args.document_role, args.role_note]):
        raise SystemExit("provide --type, --role, or --role-note")
    row = load_store().update_document_metadata(
        args.document_id,
        document_type=args.document_type,
        document_role=args.document_role,
        role_note=args.role_note,
    )
    print("updated document metadata")
    print(f"id={row['id']}")
    print(f"type={row.get('document_type') or 'unknown'}")
    print(f"role={row.get('document_role') or 'unknown'}")
    print(f"role_note={row.get('role_note') or ''}")
    return 0


def cmd_add_timeline(args: argparse.Namespace) -> int:
    store = load_store()
    item_id = store.add_timeline_item(
        document_id=args.document_id,
        event_date=args.event_date,
        event_type=args.event_type,
        title=args.title,
        body=args.body,
        source_quote=args.source_quote,
        confidence=args.confidence,
        verified_by_user=1 if args.verified else 0,
    )
    rebuild_search_index(store)
    print("added timeline item")
    print(f"id={item_id}")
    print(f"document_id={args.document_id or 'none'}")
    print(f"date={args.event_date or 'unknown'}")
    print(f"event_type={args.event_type}")
    return 0


def cmd_add_body_parameter(args: argparse.Namespace) -> int:
    store = load_store()
    parameter_id = add_body_parameter(
        store,
        document_id=args.document_id,
        timeline_item_id=args.timeline_item_id,
        observed_at=args.observed_at,
        parameter_group=args.parameter_group,
        parameter_name=args.parameter_name,
        parameter_code=args.parameter_code,
        value_text=args.value_text,
        value_numeric=args.numeric_value,
        unit=args.unit,
        reference_range=args.reference_range,
        note=args.note,
        body_site=args.body_site,
        method=args.method,
        source_quote=args.source_quote,
        confidence=args.confidence,
        verified_by_user=1 if args.verified else 0,
    )
    rebuild_search_index(store)
    print("added body parameter")
    print(f"id={parameter_id}")
    print(f"document_id={args.document_id or 'none'}")
    print(f"timeline_item_id={args.timeline_item_id or 'none'}")
    print(f"observed_at={args.observed_at}")
    print(f"parameter={args.parameter_name}")
    return 0


def cmd_body_parameters(args: argparse.Namespace) -> int:
    store = load_store()
    rows = (
        search_body_parameters(store, args.query, limit=args.limit)
        if args.query
        else list_body_parameters(store, limit=args.limit)
    )
    if not rows:
        print("no body parameters")
        return 0
    for row in rows:
        value = row.get("value_text") or ""
        if row.get("value_numeric") is not None:
            value = f"{row['value_numeric']:g} {row.get('unit') or ''}".strip()
        print(
            f"- {row.get('observed_at') or 'date unknown'} — "
            f"{row.get('parameter_name') or 'parameter unknown'}"
            + (f": {value}" if value else "")
            + (f" [{row.get('parameter_group')}]" if row.get("parameter_group") else "")
        )
        print(f"  id={row.get('id')} document_id={row.get('document_id') or 'none'} timeline_item_id={row.get('timeline_item_id') or 'none'}")
        if row.get("note"):
            print(f"  note={row['note']}")
        if row.get("source_quote"):
            print(f"  source_quote={row['source_quote']}")
    return 0


def cmd_telegram_cache_ingest(args: argparse.Namespace) -> int:
    store = load_store()
    cache_dirs = [Path(path) for path in args.cache_dir] if args.cache_dir else default_cache_dirs()
    if not cache_dirs:
        print("no Telegram cache directories found")
        return 0
    print("telegram cache dirs:")
    for path in cache_dirs:
        print(f"- {path}")
    total_seen = total_new = 0
    for results in watch_cache_dirs(store, cache_dirs, interval_seconds=args.interval, once=args.once, dry_run=args.dry_run):
        total_seen += len(results)
        for result in results:
            short_sha = result.sha256[:12] if result.sha256 else "n/a"
            doc = result.document_id or "n/a"
            print(f"{result.status} id={doc} sha={short_sha} path={result.path}" + (f" reason={result.reason}" if result.reason else ""))
            if result.status.startswith("ingested"):
                total_new += 1
        if args.once:
            break
    print(f"telegram-cache-ingest seen={total_seen} new={total_new}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "init": cmd_init,
        "ingest": cmd_ingest,
        "timeline": cmd_timeline,
        "extract": cmd_extract,
        "index": cmd_index,
        "search": cmd_search,
        "summary": cmd_summary,
        "content-audit": cmd_content_audit,
        "annotate-document": cmd_annotate_document,
        "add-timeline": cmd_add_timeline,
        "add-body-parameter": cmd_add_body_parameter,
        "body-parameters": cmd_body_parameters,
        "telegram-cache-ingest": cmd_telegram_cache_ingest,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
