# Current live system

Last verified manually: 2026-06-15.

This document describes the live system as it actually exists on `ai-server`. It is the source of truth for the current MVP state.

## High-level status

The medical assistant is live as a dedicated Hermes profile and dedicated Telegram gateway.

```text
Telegram dedicated medical bot
  -> systemd service: hermes-medical-consultant-gateway.service
  -> Hermes profile: medical_consultant
  -> medical vault CLI: /srv/hermes-medical/repo/.venv/bin/medical-agent
  -> local vault: /srv/hermes-medical/data
  -> SQLite: /srv/hermes-medical/data/db/medical.sqlite
```

There is no Docker container in the primary MVP path.

## Live profile

```text
/home/hermes/.hermes/profiles/medical_consultant
```

Important files:

```text
/home/hermes/.hermes/profiles/medical_consultant/profile.yaml
/home/hermes/.hermes/profiles/medical_consultant/SOUL.md
/home/hermes/.hermes/profiles/medical_consultant/auth.json
/home/hermes/.hermes/profiles/medical_consultant/.env
```

The `.env` for `medical_consultant` is a real file, not a symlink, because the profile uses its own dedicated Telegram bot token.

The profile reuses Hermes provider/auth credentials by copying `auth.json` from the working `kanban_operator` profile during bootstrap.

## Live gateway service

```text
/etc/systemd/system/hermes-medical-consultant-gateway.service
```

Expected service shape:

```text
[Service]
User=hermes
Group=hermes
WorkingDirectory=/srv/hermes-medical/repo
Environment=HOME=/home/hermes
Environment=PATH=/home/hermes/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=HTTP_PROXY=http://127.0.0.1:8118
Environment=HTTPS_PROXY=http://127.0.0.1:8118
Environment=NO_PROXY=127.0.0.1,localhost,::1
ExecStart=/home/hermes/.local/bin/hermes --profile medical_consultant gateway run
Restart=always
RestartSec=5
TimeoutStartSec=120
TimeoutStopSec=240
KillMode=control-group
```

## Existing parallel Hermes gateway

The existing `kanban_operator` gateway remains live and separate:

```text
hermes-kanban-operator-gateway.service
/home/hermes/.hermes/profiles/kanban_operator
```

Both gateways should run in parallel:

```text
kanban_operator       running
medical_consultant    running
```

Do not run two gateways with the same `TELEGRAM_BOT_TOKEN`. `medical_consultant` must use its own Telegram bot token.

## Medical vault

Root:

```text
/srv/hermes-medical
```

Layout:

```text
/srv/hermes-medical/
  repo/       # git clone of alldevice/personal-medical-agent
  data/       # real medical vault, never Git
  config/     # local vault config, never Git
```

Data directories:

```text
/srv/hermes-medical/data/raw
/srv/hermes-medical/data/extracted
/srv/hermes-medical/data/extracted_text
/srv/hermes-medical/data/normalized
/srv/hermes-medical/data/timeline
/srv/hermes-medical/data/db
/srv/hermes-medical/data/audit
/srv/hermes-medical/data/backups
/srv/hermes-medical/data/reports
```

SQLite database:

```text
/srv/hermes-medical/data/db/medical.sqlite
```

Current `documents` metadata includes document-role classification fields:

```text
document_role
role_note
```

The role layer is used to reduce noisy doctor-facing reports without deleting or rewriting originals. Current roles are: `clinical_source`, `treatment_order`, `referral_order`, `administrative_supporting`, `supporting_context`, `auxiliary_context`, `patient_self_report`, and `container_bundle`.

Run `medical-agent init` after pulling schema changes; it applies lightweight SQLite migrations for existing vault databases.

## Structured body-parameter layer

The live system includes a structured `body_parameters` table for source-linked, time-linked body-state facts.

The layer is used for:

- laboratory values;
- vital signs;
- ECG and functional-study measurements;
- imaging and ultrasound findings;
- endoscopy/procedure findings;
- examination findings;
- symptoms, medication self-reports, and allergy self-reports when source-grounded.

Each row should preserve `observed_at`, `document_id`, `timeline_item_id` when available, parameter name, numeric or text value, unit, reference range, source quote, confidence, and cautious notes for OCR/self-report uncertainty.

The FTS index includes `body_parameters` with scope `body_parameter`, alongside `document_text` and `timeline_note` rows.

Current private archive verification reports and backups are stored under `/srv/hermes-medical/data/audit`, `/srv/hermes-medical/data/reports`, and `/srv/hermes-medical/data/backups`; they are intentionally not committed to Git.

## Runtime users

```text
aiadmin/root:
  system setup, apt, systemd, permissions, service management

hermes:
  owns and runs Hermes profiles
  owns /srv/hermes-medical/repo
  owns /srv/hermes-medical/data
  owns /srv/hermes-medical/config
```

`hermes` must not be added to the Docker group for this MVP.

## Working CLI

CLI path:

```text
/srv/hermes-medical/repo/.venv/bin/medical-agent
```

Available commands:

```text
medical-agent init
medical-agent ingest
medical-agent timeline
medical-agent extract
medical-agent index
medical-agent search
medical-agent summary
medical-agent content-audit
medical-agent annotate-document
medical-agent add-timeline
medical-agent add-body-parameter
medical-agent body-parameters
medical-agent telegram-cache-ingest
```

Smoke test command:

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent body-parameters --limit 5
```

## Telegram verification

The dedicated medical Telegram bot has answered correctly as:

```text
Hermes Agent in profile medical_consultant
```

The bot may ask for home channel setup. Use:

```text
/sethome
```

## Honcho conversational memory

Honcho conversational memory is live for the `medical_consultant` Telegram profile.

Runtime identity:

```text
workspace: hermes_medical_consultant
host key: hermes.medical_consultant
canonical Human peer: human_sergei
Telegram runtime alias: 237187787 -> human_sergei
agent peer: hermes_medical_consultant
pinPeerName: false
```

Scope:

- Honcho is used for conversational/context memory only.
- Honcho can remember stable communication preferences, answer style, workflow preferences, and doctor-preparation style.
- Honcho is not the medical source of truth.
- Medical facts must remain grounded in `/srv/hermes-medical/data/raw`, `/srv/hermes-medical/data/db/medical.sqlite`, timeline entries, body parameters, extracted working copies, or explicit current user messages.
- If a medical claim comes only from Honcho memory, the assistant must label it as conversation memory and not document-confirmed.

Historical note: early pre-alias Honcho rows may contain peer `237187787`. New medical traffic after the alias repair should use `human_sergei`.

## Current limitations

- Telegram attachment-to-vault ingest is implemented through cache ingest/timer support, with caption/cache policy and Telegram UX still improving.
- Extracted working copies, text extraction, OCR hook, SQLite FTS search, document-role metadata, content audit, and structured `body_parameters` now exist as CLI/data-layer capabilities.
- Telegram commands for search/summary, direct body-parameter views, and deeper medical comparison workflows are not yet integrated into the live bot.
- Honcho conversational memory is integrated, but only as non-authoritative conversation/context memory.
- Multi-user mode is not yet implemented.
- Postgres is not yet used; SQLite is the current database.
- Docker is intentionally not in the primary MVP path.
