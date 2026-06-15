# Body-parameter indexing status

Date: 2026-06-15

## Status

Structured body-parameter indexing is implemented and operational for the current private archive snapshot.

This document intentionally describes the product capability and operational workflow only. Private medical values, document ids, generated reports, backups, and extracted archive content remain under `/srv/hermes-medical/data` on the live server and must not be committed to Git.

## Implemented capabilities

- SQLite table: `body_parameters`.
- CLI commands:
  - `medical-agent add-body-parameter`
  - `medical-agent body-parameters`
- FTS scope:
  - `body_parameter`
- Links:
  - `document_id` links a parameter back to the immutable source document.
  - `timeline_item_id` links a parameter to a source-linked event when available.
- Supported source-grounded groups:
  - `lab`
  - `vital`
  - `ecg`
  - `imaging`
  - `exam`
  - `symptom`
  - `medication`
  - `other`

## Operational acceptance

The live private archive went through three indexing batches and a final independent search audit on 2026-06-15.

Acceptance criteria used:

- raw originals were not modified;
- no diagnosis or treatment advice was added as a recommendation;
- source-grounded values and qualitative findings were linked to source documents;
- self-reports and OCR/uncertain rows used conservative confidence and notes;
- FTS was rebuilt after indexing;
- final targeted search audit returned body-parameter hits for representative lab, ECG, vital-sign, imaging, endoscopy, procedure, allergy, medication, and exam queries;
- consistency checks found no orphan extracted-text rows, timeline links, document links, or body-parameter timeline links.

## Local operational artifacts

Private audit reports and backups are kept only on the live server, for example:

    /srv/hermes-medical/data/audit/final_body_parameter_search_audit_*.md
    /srv/hermes-medical/data/audit/post_body_parameters_batch*_verification_*.md
    /srv/hermes-medical/data/backups/post-body-parameters-batch*

These files may contain private medical context and must not be committed.

## Ongoing work

Future work should focus on:

- running the same indexing workflow for newly ingested documents;
- improving Telegram-facing search/summary commands that can safely surface `body_parameter` rows;
- adding duplicate-prevention and QA helpers for future indexing batches;
- building doctor-preparation packets from source-linked documents, timeline items, and body parameters;
- keeping self-report, OCR, and low-confidence rows clearly labeled.
