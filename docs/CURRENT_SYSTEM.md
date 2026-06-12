# Current live system

Last verified manually: 2026-06-12.

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

```ini
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
/srv/hermes-medical/data/extracted_text
/srv/hermes-medical/data/normalized
/srv/hermes-medical/data/timeline
/srv/hermes-medical/data/db
/srv/hermes-medical/data/audit
/srv/hermes-medical/data/backups
```

SQLite database:

```text
/srv/hermes-medical/data/db/medical.sqlite
```

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
```

Smoke test command:

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
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
- Medical facts must remain grounded in `/srv/hermes-medical/data/raw`, `/srv/hermes-medical/data/db/medical.sqlite`, timeline entries, extracted working copies, or explicit current user messages.
- If a medical claim comes only from Honcho memory, the assistant must label it as conversation memory and not document-confirmed.

Historical note: early pre-alias Honcho rows may contain peer `237187787`. New medical traffic after the alias repair should use `human_sergei`.

## Current limitations

- Telegram attachment-to-vault ingest is not yet fully automated end-to-end.
- Raw files and SQLite exist locally; text extraction/OCR is future work.
- Search over stored content is not yet implemented.
- Honcho conversational memory is integrated, but only as non-authoritative conversation/context memory.
- Multi-user mode is not yet implemented.
- Postgres is not yet used; SQLite is the current database.
- Docker is intentionally not in the primary MVP path.
