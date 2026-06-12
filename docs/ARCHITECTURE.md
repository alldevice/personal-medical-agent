# Architecture

## Principle

Docker contains tools. The mounted data volume contains life.

## Components

- Telegram bot: single MVP interface.
- Medical store: local filesystem vault plus SQLite index.
- Ingest pipeline: receive file, store original, hash, parse caption, create timeline event.
- Future extractor: PDF text, OCR, DICOM metadata, ECG raw signal parsing.
- Future retrieval: SQLite full-text search and optional vector index.
- Future Hermes integration: Hermes profile runs inside the container or calls this bot/CLI as a tool.

## Data boundaries

- Never commit real medical data.
- Never commit Telegram/OpenAI/provider credentials.
- Keep `config/.env` local.
- Keep `data/` local.
