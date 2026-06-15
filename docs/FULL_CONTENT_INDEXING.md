# Full content indexing contract

Date: 2026-06-15

This document defines the import and indexing contract for archive-like medical source files.

## Problem

A source filename can describe only a transport container or a formal cover document. It must not be treated as the full clinical description of the source.

Examples of risky source titles include generic reports, result bundles, referrals, discharge papers, archive files, and scanned document packets. A bundle can contain several different source facts even when the outer filename suggests only one document.

## Contract

For every new and existing source file, the system must preserve the immutable original and also make the inner content discoverable.

Required behavior:

- keep the original file unchanged under `/srv/hermes-medical/data/raw`;
- materialize a stable working copy under `/srv/hermes-medical/data/extracted/<document_id>/files`;
- recursively expand nested ZIP archives within a conservative depth and file-count limit;
- write a manifest that links every working copy back to the source document id and raw source;
- extract searchable text into `/srv/hermes-medical/data/extracted_text` where possible;
- record extraction failures or empty output without deleting the source;
- rebuild SQLite FTS from extracted text, timeline notes, and structured `body_parameters`;
- update `document_type`, `document_role`, and `role_note` when a source is a composite bundle;
- add multiple source-linked timeline items when one source contains multiple important internal blocks;
- add source-linked `body_parameters` for concrete body-state facts when present.

The original source remains one document row. Additional timeline rows and body-parameter rows can point to the same `document_id`.

## CLI workflow

Refresh the full archive index:

```bash
medical-agent extract --all
medical-agent index --all
medical-agent content-audit --limit 300 --stdout
```

Annotate a composite source without changing the raw file:

```bash
medical-agent annotate-document --id <document_id> --type "composite clinical source" --role clinical_source --role-note "contains multiple source blocks; see linked timeline items"
```

Add a timeline item for an internal block in a composite source:

```bash
medical-agent add-timeline --document-id <document_id> --date YYYY-MM-DD --event-type <event_type> --title "Short source-linked title" --body "Source-grounded summary of the internal block" --quote "Short source quote if available"
```

Use conservative event types such as `lab_result`, `imaging`, `ecg`, `consultation`, `hospital_visit`, `procedure`, or `other`.

Add a structured body-state fact for an internal block:

```bash
medical-agent add-body-parameter --document-id <document_id> --timeline-item-id <timeline_item_id> --observed-at YYYY-MM-DD --group <lab|vital|ecg|imaging|exam|symptom|medication|other> --parameter "Parameter name" --numeric-value <number-if-numeric> --value "exact text if qualitative" --unit "unit if present" --reference-range "range if present" --quote "short source quote" --confidence <0.3-1.0>
```

List or search structured body-state facts:

```bash
medical-agent body-parameters --limit 50
medical-agent body-parameters --query "гемоглобин"
```

## Audit output

`medical-agent content-audit` writes a Markdown report under:

```text
/srv/hermes-medical/data/audit
```

The report highlights:

- total document count;
- archive/container count;
- documents with extracted manifests;
- documents with extracted text;
- candidate bundles;
- records needing manual review.

## Search acceptance

After extraction, indexing, semantic annotation, and body-parameter indexing, a clinically relevant source must be findable by content terms even if the outer filename is generic.

Negative search results should not be trusted until:

1. `extract --all` completed;
2. `index --all` completed;
3. `content-audit` was reviewed;
4. empty/failed OCR or text extraction cases were either fixed or marked for review;
5. expected body-state facts were indexed as source-linked `body_parameters` where appropriate.

## Safety boundary

This workflow improves source discovery only. It does not diagnose, prescribe, or turn OCR output into confirmed medical fact. OCR text, AI-generated timeline summaries, and body-parameter rows must remain traceable to the source document and should preserve uncertainty when text quality is low.
