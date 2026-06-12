# Architecture

## MVP principle

Use the existing Hermes ecosystem first. Do not create a separate Docker runtime for the MVP.

```text
Telegram dedicated medical bot
  -> systemd: hermes-medical-consultant-gateway.service
  -> Hermes profile: medical_consultant
  -> local CLI: /srv/hermes-medical/repo/.venv/bin/medical-agent
  -> local vault: /srv/hermes-medical/data
  -> SQLite: /srv/hermes-medical/data/db/medical.sqlite
```

## Components

- `medical_consultant` Hermes profile: user-facing medical archive assistant.
- Dedicated Telegram bot token: stored only in `/home/hermes/.hermes/profiles/medical_consultant/.env`.
- Gateway service: `/etc/systemd/system/hermes-medical-consultant-gateway.service`.
- Shared provider/auth credentials: copied from the `kanban_operator` profile auth file when bootstrapping.
- Local CLI: deterministic storage operations (`init`, `ingest`, `timeline`).
- Medical store: filesystem vault plus SQLite index.
- Raw storage: original PDFs/images/DICOM/ECG files kept unchanged.
- Timeline: chronological source-linked medical events.
- Future extraction: PDF text, OCR, DICOM metadata, ECG raw signal parsing.
- Future retrieval: SQLite FTS and optional vector index/Honcho integration.

## User and permission model

- `aiadmin`/root: server setup, apt, systemd, firewall, permissions.
- `hermes`: owns `/srv/hermes-medical/repo`, `/srv/hermes-medical/data`, `/srv/hermes-medical/config`, and `/home/hermes/.hermes/profiles/medical_consultant`.
- `hermes` should not be added to the Docker group for this MVP.

## Data boundaries

- Never commit real medical data.
- Never commit Telegram/OpenAI/provider credentials.
- Keep `/srv/hermes-medical/config/.env` local.
- Keep `/srv/hermes-medical/data/` local.
- Keep `/home/hermes/.hermes/profiles/medical_consultant/.env` local.

## Honcho conversational memory

The live medical contour uses Honcho as a conversational memory layer, not as a clinical source-of-truth store.

```text
Telegram medical bot
  -> Hermes profile: medical_consultant
  -> Honcho workspace: hermes_medical_consultant
  -> Human peer alias: 237187787 -> human_sergei
  -> Agent peer: hermes_medical_consultant
```

Honcho may hold durable interaction memory:

- answer style and language preferences;
- user workflow preferences;
- doctor-preparation style;
- non-authoritative conversation continuity.

Honcho must not be used as authoritative storage for raw medical files, lab values, prescriptions, diagnoses, images, or clinical records. Those remain in the local vault and SQLite/extracted-data layers.

## Future Docker mode

Docker can be reintroduced later as a packaging/distribution mode. It is intentionally not the primary MVP path.
