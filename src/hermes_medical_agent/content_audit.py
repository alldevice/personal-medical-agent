from __future__ import annotations

import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from hermes_medical_agent.search_index import ensure_search_schema
from hermes_medical_agent.storage import MedicalStore

GENERIC_TITLE_TERMS = ("conclusion", "result", "report", "referral", "archive", "document")
SIGNAL_TERMS = ("ecg", "lab", "blood", "glucose", "ultrasound", "x-ray", "ct", "mri", "icd")


@dataclass(frozen=True)
class ContentAuditReport:
    generated_at: str
    total_documents: int
    zip_documents: int
    manifest_count: int
    extracted_text_count: int
    needs_review_count: int
    composite_candidate_count: int
    rows: tuple[dict[str, object], ...]


def build_content_audit_report(store: MedicalStore) -> ContentAuditReport:
    ensure_search_schema(store.db_path)
    rows: list[dict[str, object]] = []
    with sqlite3.connect(store.db_path) as con:
        con.row_factory = sqlite3.Row
        documents = con.execute(
            """
            SELECT d.id, d.original_filename, d.stored_path, d.mime_type,
                   d.document_type, d.document_date, d.document_role, d.role_note,
                   d.processing_status,
                   COALESCE(et.extracted_text_path, d.extracted_text_path) AS extracted_text_path,
                   et.extraction_method, et.quality_flag
            FROM documents d
            LEFT JOIN extracted_texts et ON et.document_id = d.id
            ORDER BY COALESCE(d.document_date, d.received_at) ASC
            """
        ).fetchall()

    for row in documents:
        document_id = str(row["id"])
        stored_path = Path(str(row["stored_path"]))
        text_path = Path(str(row["extracted_text_path"])) if row["extracted_text_path"] else None
        text = _read_optional_text(text_path)
        title_blob = " ".join(str(value or "") for value in [row["original_filename"], row["document_type"], row["role_note"]])
        quality = str(row["quality_flag"] or "missing")
        is_zip = _is_zip(stored_path, str(row["mime_type"] or ""))
        manifest_exists = (store.extracted_dir / document_id / "manifest.json").exists()
        text_exists = bool(text_path and text_path.exists())
        generic_title = _contains_any(title_blob, GENERIC_TITLE_TERMS)
        signals = _contains_any(text + "\n" + title_blob, SIGNAL_TERMS)

        reasons: list[str] = []
        if is_zip:
            reasons.append("archive/container source")
        if generic_title:
            reasons.append("generic or incomplete title")
        if not manifest_exists:
            reasons.append("missing extracted manifest")
        if not text_exists:
            reasons.append("missing extracted_text")
        if quality in {"missing", "empty", "failed", "partial"}:
            reasons.append(f"text quality={quality}")
        if signals:
            reasons.append("keyword signals present")
        if not row["document_role"]:
            reasons.append("missing document_role")
        if not row["role_note"]:
            reasons.append("missing role_note")

        composite_candidate = bool(is_zip or (generic_title and signals))
        needs_review = bool(
            composite_candidate or not manifest_exists or not text_exists
            or quality in {"missing", "empty", "failed", "partial"}
            or not row["document_role"] or not row["role_note"]
        )
        rows.append({
            "document_id": document_id,
            "date": str(row["document_date"] or ""),
            "filename": str(row["original_filename"] or ""),
            "type": str(row["document_type"] or ""),
            "quality": quality,
            "chars": len(text),
            "reasons": reasons,
            "needs_review": needs_review,
            "composite_candidate": composite_candidate,
            "is_zip": is_zip,
            "manifest_exists": manifest_exists,
            "extracted_text_exists": text_exists,
        })

    return ContentAuditReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_documents=len(rows),
        zip_documents=sum(1 for row in rows if row["is_zip"]),
        manifest_count=sum(1 for row in rows if row["manifest_exists"]),
        extracted_text_count=sum(1 for row in rows if row["extracted_text_exists"]),
        needs_review_count=sum(1 for row in rows if row["needs_review"]),
        composite_candidate_count=sum(1 for row in rows if row["composite_candidate"]),
        rows=tuple(rows),
    )


def render_content_audit_markdown(report: ContentAuditReport, *, limit: int = 100) -> str:
    lines = [
        "# Full content indexing audit", "", f"Generated at: `{report.generated_at}`", "",
        "## Summary", "", f"- total_documents: {report.total_documents}",
        f"- zip_documents: {report.zip_documents}",
        f"- documents_with_manifest: {report.manifest_count}",
        f"- documents_with_extracted_text: {report.extracted_text_count}",
        f"- needs_review: {report.needs_review_count}",
        f"- composite_candidates: {report.composite_candidate_count}", "",
        "## Candidate rows", "",
        "| document_id | date | filename | type | quality | chars | reasons |",
        "|---|---:|---|---|---|---:|---|",
    ]
    candidates = [row for row in report.rows if row["needs_review"] or row["composite_candidate"]]
    if not candidates:
        lines.append("| none |  |  |  |  | 0 | no candidates found |")
    for row in candidates[:limit]:
        lines.append(
            "| " + " | ".join([
                _md(str(row["document_id"])), _md(str(row["date"])), _md(str(row["filename"])),
                _md(str(row["type"])), _md(str(row["quality"])), str(row["chars"]),
                _md("; ".join(str(item) for item in row["reasons"])),
            ]) + " |"
        )
    lines.extend([
        "", "## Notes", "",
        "- A ZIP filename is a transport/container label, not a clinical description.",
        "- Run `medical-agent extract --all` and `medical-agent index --all` before trusting negative search results.",
        "- Composite sources may need several timeline items pointing to one document id.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def write_content_audit_report(store: MedicalStore, report: ContentAuditReport | None = None, *, limit: int = 100) -> Path:
    active_report = report or build_content_audit_report(store)
    audit_dir = store.data_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = audit_dir / f"full_content_indexing_audit_{stamp}.md"
    path.write_text(render_content_audit_markdown(active_report, limit=limit), encoding="utf-8")
    return path


def _is_zip(path: Path, mime_type: str) -> bool:
    if path.suffix.lower() == ".zip" or "zip" in mime_type.casefold():
        return True
    try:
        return path.exists() and path.is_file() and zipfile.is_zipfile(path)
    except OSError:
        return False


def _read_optional_text(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(needle.casefold() in lowered for needle in needles)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
