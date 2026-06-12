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
