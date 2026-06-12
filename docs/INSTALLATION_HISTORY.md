# Installation history

This document records the MVP installation sequence performed on `ai-server`.

## 1. Repository approach changed

Initial repository skeleton included Docker files and a standalone Telegram bot path. The live architecture was changed to:

```text
existing Hermes runtime
  + dedicated profile: medical_consultant
  + dedicated Telegram bot token
  + local vault under /srv/hermes-medical
  + CLI tools from this repository
```

Docker is not used in the primary MVP path.

## 2. Server directories created

Root layout:

```text
/srv/hermes-medical/
  repo/
  data/
  config/
```

The `hermes` user owns runtime files. `aiadmin`/root performed setup.

## 3. Repository cloned with SSH

HTTPS clone failed because GitHub does not support password authentication for Git operations.

Working clone command:

```bash
sudo -u hermes -H git clone git@github.com:alldevice/personal-medical-agent.git /srv/hermes-medical/repo
```

The `hermes` user already had working SSH authentication to GitHub.

## 4. Local config created

```text
/srv/hermes-medical/config/.env
```

This file contains local vault settings, not the Telegram bot token.

Current profile setting:

```text
HERMES_MEDICAL_PROFILE=medical_consultant
```

## 5. Python CLI installed

Virtualenv:

```text
/srv/hermes-medical/repo/.venv
```

CLI:

```text
/srv/hermes-medical/repo/.venv/bin/medical-agent
```

Installed with:

```bash
sudo -u hermes -H python3 -m venv /srv/hermes-medical/repo/.venv
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/python -m pip install --upgrade pip
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
```

## 6. SQLite vault initialized

Command:

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
```

Created:

```text
/srv/hermes-medical/data/db/medical.sqlite
```

## 7. Manual ingest smoke test passed

A synthetic test document was ingested:

```text
type: test-document
date: 2026-06-12
comment: MVP smoke test
```

The timeline returned:

```text
2026-06-12 — test-document: MVP smoke test
```

## 8. Hermes profile created

Profile name:

```text
medical_consultant
```

Path:

```text
/home/hermes/.hermes/profiles/medical_consultant
```

Files created/verified:

```text
profile.yaml
SOUL.md
auth.json
.env
```

At first, `.env` was made like `kanban_operator` as a symlink to shared `.env`. After choosing the dedicated Telegram bot approach, it was converted to a real separate profile `.env` so the medical bot can use its own token.

## 9. Dedicated Telegram bot selected

The user created a second Telegram bot for the medical assistant.

Reason: running two Hermes gateways against the same `TELEGRAM_BOT_TOKEN` would conflict. Therefore `medical_consultant` uses its own token.

The token is stored only on the server:

```text
/home/hermes/.hermes/profiles/medical_consultant/.env
```

## 10. Systemd gateway service created

Service:

```text
/etc/systemd/system/hermes-medical-consultant-gateway.service
```

Expected command:

```text
/home/hermes/.local/bin/hermes --profile medical_consultant gateway run
```

Service status after setup:

```text
Active: active (running)
```

Hermes gateway list showed:

```text
kanban_operator       running
medical_consultant    running
```

## 11. Telegram smoke test passed

The user sent:

```text
/start
Привет. Кто ты и какой у тебя профиль?
```

The bot replied that it is Hermes Agent profile `medical_consultant`, a personal assistant for medical archive, document chronology, and doctor-preparation, and that it does not replace a doctor.

## 12. Current source-of-truth documents

- `docs/CURRENT_SYSTEM.md`
- `docs/RUNBOOK.md`
- `docs/OPERATIONS.md`
- `docs/CHANGE_MANAGEMENT.md`
- `docs/ROADMAP.md`
- `docs/INSTALLATION_HISTORY.md`
