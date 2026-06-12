# Roadmap

This roadmap captures planned future work for the personal medical consultant system.

Status labels:

```text
Now       next practical MVP work
Next      planned after MVP is stable
Later     larger architecture change
Research  needs investigation before implementation
```

## Now: stabilize live MVP

### 1. End-to-end Telegram attachment ingest

Status: Now

Goal: send a PDF/photo to the dedicated medical Telegram bot and have it stored automatically in the local vault.

Acceptance:

- Telegram attachment is saved to a local temporary path.
- `medical-agent ingest` is called automatically.
- Original file is stored under `/srv/hermes-medical/data/raw/YYYY/MM/DD/`.
- SQLite row is created.
- Timeline item is created.
- Telegram reply includes document id, type/date if known, and SHA-256 prefix.
- Temporary files are cleaned up.

### 2. Better caption parser

Status: Now

Support Russian and English fields:

```text
type / тип / вид / документ
date / дата
comment / комментарий / заметка
body_part / орган / область
clinic / клиника
```

Acceptance:

- Unknown fields do not break ingest.
- Missing date/type is stored as unknown and reported to user.

### 3. Basic document listing and deletion workflow

Status: Now

Commands:

```text
/timeline
/documents
/document <id>
/delete_document <id>
```

Deletion should be conservative:

- default: mark as deleted/archived;
- physical deletion only after explicit confirmation.

### 4. Backup and restore runbook

Status: Now

Define backup process for:

```text
/srv/hermes-medical/data
/srv/hermes-medical/config
/home/hermes/.hermes/profiles/medical_consultant/profile.yaml
/home/hermes/.hermes/profiles/medical_consultant/SOUL.md
```

Acceptance:

- backup command exists;
- restore command exists;
- restore is tested on a copy, not directly on live data.

## Next: retrieval and extraction

### 5. PDF text extraction

Status: Next

Use `pypdf` for text-based PDFs.

Acceptance:

- extracted text stored under `/srv/hermes-medical/data/extracted_text`;
- source document id is preserved;
- extraction failures are recorded but do not block storing raw files.

### 6. OCR for photos and scanned PDFs

Status: Next

Use local OCR tools first. Keep OCR output clearly separated from original source facts.

Acceptance:

- OCR text is stored as extracted data;
- confidence/quality flag is recorded;
- user can ask the agent to explain that OCR may be wrong.

### 7. SQLite full-text search

Status: Next

Add FTS over extracted text and timeline notes.

Commands:

```text
/search <query>
/summary <topic>
```

Acceptance:

- search returns source document ids;
- answer distinguishes exact source text, extracted text, and interpretation.

### 8. Timeline normalization

Status: Next

Normalize medical events:

```text
lab_result
imaging
procedure
consultation
medication
symptom
hospital_visit
other
```

Acceptance:

- timeline can be filtered by event type;
- events can link to one or more documents.

## Later: structured medical data

### 9. Lab results parser

Status: Later

Extract structured values from common lab reports.

Schema idea:

```text
analyte
value
unit
reference_range
flag
sample_date
source_document_id
```

Acceptance:

- values are traceable to source documents;
- no medical conclusion is stored as fact unless it is in the source.

### 10. Medication and allergy list

Status: Later

Track user-confirmed medications, allergies, intolerances, and contraindication notes.

Acceptance:

- user confirmation required before facts become durable;
- agent can prepare a doctor-facing summary.

### 11. Doctor visit preparation mode

Status: Later

Generate concise doctor-preparation packets:

```text
problem summary
key dates
documents to bring
questions to ask
red flags to mention
uncertainties
```

Acceptance:

- always source-linked;
- avoids diagnosis/prescription language.

## Memory and personalization

### 12. Honcho memory integration

Status: Research

Use Honcho for interaction memory and preference memory, not as the medical source of truth.

Good candidates for Honcho:

```text
preferred answer style
language preference
known communication constraints
user preference for calm concise answers
recurring doctor-preparation style
```

Not for Honcho:

```text
raw medical documents
lab values as authoritative facts
medical images
full clinical records
```

Acceptance:

- source medical facts remain in vault/SQLite;
- Honcho memory can be rebuilt or ignored without data loss;
- user can review/delete memory entries.

### 13. Agent self-feedback / disagreement log

Status: Research

Capture cases where the agent is uncertain or sees conflict between sources.

Acceptance:

- uncertainty is stored as agent note, not medical fact;
- source conflict list can be shown to user;
- user can use it to improve prompts, docs, or structured data.

## Database evolution

### 14. Postgres migration

Status: Later

SQLite is enough for the current single-user MVP. Postgres becomes useful when:

- multi-user mode is needed;
- concurrent writes increase;
- external services need controlled DB access;
- advanced search/vector extensions are needed.

Acceptance:

- migration script exists;
- SQLite backup is taken before migration;
- rollback plan exists;
- no raw files are stored inside Postgres by default.

### 15. Vector index

Status: Later

Optional retrieval layer for extracted text. It must never replace source-linked retrieval.

Acceptance:

- vector hit always links back to source document id;
- source snippets are shown before interpretation;
- index can be rebuilt from raw/extracted data.

## Multi-user and access control

### 16. Multi-user mode

Status: Later

Initial system is personal/single-user. Multi-user mode requires explicit access boundaries.

Needed concepts:

```text
user_id
household_id or care_group_id
document owner
document visibility
consent and delegation
role: owner / viewer / caregiver / admin
```

Acceptance:

- one user's documents cannot leak into another user's answers;
- every query is scoped to an authorized user/context;
- audit log records access.

### 17. Family/caregiver mode

Status: Later

Allow a trusted family member/caregiver to view or add documents with permission.

Acceptance:

- explicit user approval;
- revocation path;
- audit trail.

## Security, privacy, and audit

### 18. Audit log

Status: Next

Track document ingest, deletion, export, and high-risk access actions.

Acceptance:

- audit records are append-only for normal operations;
- no secrets in logs;
- no full medical file content in logs.

### 19. Export package

Status: Later

Create a doctor-facing or user-facing export.

Acceptance:

- selected documents only;
- timeline summary;
- manifest with SHA-256;
- clear warning that it is not a diagnosis.

### 20. Encryption at rest

Status: Research

Evaluate whether to encrypt the vault or selected backups.

Acceptance:

- documented key management;
- tested restore;
- no lockout risk from forgotten keys.

## Packaging and deployment

### 21. Optional Docker mode

Status: Later

Docker can return as an optional packaging mode, not the primary local MVP path.

Use cases:

- OCR/DICOM dependencies;
- distribution to another server;
- reproducible extraction workers.

Acceptance:

- Docker does not require `hermes` to be in the Docker group;
- real data remains mounted from `/srv/hermes-medical/data`;
- docs clearly distinguish Docker packaging from live non-Docker MVP.

### 22. Background extraction worker

Status: Later

Separate long-running or scheduled worker for OCR/text extraction.

Acceptance:

- gateway remains responsive;
- extraction jobs are idempotent;
- failed extraction can be retried.

## GitHub project hygiene

### 23. GitHub Issues for roadmap items

Status: Next

Convert roadmap sections into GitHub issues when work begins.

Suggested labels:

```text
area:telegram
area:vault
area:search
area:memory
area:database
area:security
area:ops
priority:now
priority:next
priority:later
```

### 24. CI checks

Status: Next

Add GitHub Actions for:

```text
pytest
ruff
secret scanning sanity checks
no-large-files check
```

Acceptance:

- PR cannot accidentally add obvious secrets;
- tests run on every PR.
