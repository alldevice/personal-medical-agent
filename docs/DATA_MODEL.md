# Data Model MVP

## Vault file layers

The vault uses a layered storage model:

- `/srv/hermes-medical/data/raw` — immutable originals exactly as received from the user. A ZIP stays a ZIP; a PDF stays a PDF.
- `/srv/hermes-medical/data/extracted/<document_id>/files` — one-time materialized working copy for fast access. ZIP members are flattened into short safe filenames; non-ZIP originals are copied here too.
- `/srv/hermes-medical/data/extracted/<document_id>/manifest.json` — machine-readable link from working files back to the raw source path and SHA-256.
- `/srv/hermes-medical/data/extracted_text` — future text/OCR output for search and summaries.
- `/srv/hermes-medical/data/db/medical.sqlite` — SQLite metadata and timeline.

Medical data directories are outside the Git repository and must not be committed.

## documents

One row per original file received from Telegram.

Key fields:

- id
- telegram_user_id
- telegram_message_id
- original_filename
- stored_path
- sha256
- mime_type
- document_type
- document_date
- user_comment
- processing_status

## timeline_items

One row per extracted or user-entered medical event.

Key fields:

- id
- document_id
- event_date
- event_type
- title
- body
- source_quote
- confidence
- verified_by_user

## Patient self-reports

Self-reports are first-class source records for patient-provided information that is clinically relevant but not independently verified by an attached medical document.

Examples:

- medication intake as actually performed by the patient;
- allergies, suspected allergies, and later uncertainty corrections;
- symptoms, side effects, home measurements, subjective status updates;
- practical decisions made while awaiting a doctor visit.

Representation:

- `documents.document_type` should start with `самоотчёт пациента:` followed by the topic.
- `documents.user_comment` and `timeline_items.body` should start with `Со слов пациента:`.
- `timeline_items.confidence` should not imply external verification unless a clinician/source document confirms it.
- Uncertainty must be stored explicitly in the text, e.g. `вероятно`, `точный препарат не подтверждён`, `примерно`, `пациент не помнит`.
- Later corrections should be added as new self-report documents; older timeline wording may be softened so summaries do not preserve an overstated claim.

Self-reports do not replace source medical documents. They are a patient-reported layer for chronology, doctor preparation, and safety flags that need cautious wording.
