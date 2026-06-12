# Architecture

## MVP principle

Use the existing Hermes ecosystem first. Do not create a separate Docker runtime for the MVP.

```text
existing Hermes Telegram gateway
  -> Hermes profile: medical_agent
  -> local CLI: /srv/hermes-medical/repo/.venv/bin/medical-agent
  -> local vault: /srv/hermes-medical/data
  -> SQLite: /srv/hermes-medical/data/db/medical.sqlite
```

## Components

- `medical_agent` Hermes profile: user-facing medical archive assistant.
- Local CLI: deterministic storage operations (`init`, `ingest`, `timeline`).
- Medical store: filesystem vault plus SQLite index.
- Raw storage: original PDFs/images/DICOM/ECG files kept unchanged.
- Timeline: chronological source-linked medical events.
- Future extraction: PDF text, OCR, DICOM metadata, ECG raw signal parsing.
- Future retrieval: SQLite FTS and optional vector index/Honcho integration.

## User and permission model

- `aiadmin`/root: server setup, apt, systemd, firewall, permissions.
- `hermes`: owns `/srv/hermes-medical/repo`, `/srv/hermes-medical/data`, `/srv/hermes-medical/config`.
- `hermes` should not be added to the Docker group for this MVP.

## Data boundaries

- Never commit real medical data.
- Never commit Telegram/OpenAI/provider credentials.
- Keep `/srv/hermes-medical/config/.env` local.
- Keep `/srv/hermes-medical/data/` local.

## Future Docker mode

Docker can be reintroduced later as a packaging/distribution mode. It is intentionally not the primary MVP path.
