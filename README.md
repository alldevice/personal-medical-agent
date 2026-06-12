# Personal Medical Agent for Hermes

Telegram-first personal medical archive and retrieval workflow implemented as a **Hermes profile + local vault + small CLI tools**.

This repository is the source of truth for the personal medical consultant system: current live state, installation history, operations, change management, and roadmap.

## Current live MVP

The MVP does **not** run its own Docker container. It uses the existing Hermes runtime/provider credentials and a separate Telegram bot token for the dedicated `medical_consultant` gateway.

```text
Telegram dedicated medical bot
  -> systemd service: hermes-medical-consultant-gateway.service
  -> Hermes profile: medical_consultant
  -> medical vault CLI: /srv/hermes-medical/repo/.venv/bin/medical-agent
  -> local vault: /srv/hermes-medical/data
  -> SQLite: /srv/hermes-medical/data/db/medical.sqlite
```

Server layout:

```text
/srv/hermes-medical/
  repo/       # git clone of this repository
  data/       # real medical vault, never Git
  config/     # local medical settings, never Git
```

Live Hermes profile:

```text
/home/hermes/.hermes/profiles/medical_consultant
```

Live gateway service:

```text
/etc/systemd/system/hermes-medical-consultant-gateway.service
```

## Documentation map

Read these files first:

- [`docs/CURRENT_SYSTEM.md`](docs/CURRENT_SYSTEM.md) — current live system source of truth.
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — installation and verification runbook.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — daily operations, restart, health checks, troubleshooting.
- [`docs/CHANGE_MANAGEMENT.md`](docs/CHANGE_MANAGEMENT.md) — how to change the system using branches, PRs, Git pull, and server updates.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — planned future work.
- [`docs/INSTALLATION_HISTORY.md`](docs/INSTALLATION_HISTORY.md) — what was done during the initial MVP setup.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture overview.
- [`docs/SAFETY_POLICY.md`](docs/SAFETY_POLICY.md) — medical safety boundary.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — current data model notes.

## MVP goals

- Keep a dedicated Hermes profile named `medical_consultant`.
- Run it through a dedicated Telegram bot/gateway so it does not conflict with `kanban_operator`.
- Store original medical files under `/srv/hermes-medical/data/raw/`.
- Calculate SHA-256 for every stored source file.
- Keep a SQLite index at `/srv/hermes-medical/data/db/medical.sqlite`.
- Build a simple chronological medical timeline.
- Let the Hermes profile answer via Telegram using the local vault as source material.
- Keep real medical data, tokens, OAuth state and provider credentials outside Git.

## Server ownership model

Recommended users:

```text
aiadmin/root:
  system setup, apt packages, permissions, systemd if needed

hermes:
  owns /srv/hermes-medical/repo
  owns /srv/hermes-medical/data
  owns /srv/hermes-medical/config
  owns /home/hermes/.hermes/profiles/medical_consultant
  runs the medical CLI from the Hermes profile
```

Do not add `hermes` to the Docker group for this MVP.

## Quick health check

```bash
cd /
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
sudo -u hermes -H bash -lc 'export HOME=/home/hermes; export PATH=/home/hermes/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; /home/hermes/.local/bin/hermes gateway list'
```

Expected:

```text
kanban_operator       running
medical_consultant    running
```

## Normal update from GitHub to server

After a PR is merged to `main`:

```bash
cd /
sudo -u hermes -H git -C /srv/hermes-medical/repo status --short
sudo -u hermes -H git -C /srv/hermes-medical/repo pull --ff-only
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
sudo systemctl restart hermes-medical-consultant-gateway.service
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
```

## Safety boundary

This system is a personal archive and assistant. It does not diagnose, prescribe, cancel medication, or replace medical care. Answers must distinguish source facts from model interpretation.

## Never commit

```text
/srv/hermes-medical/data/**
/srv/hermes-medical/config/.env
/home/hermes/.hermes/profiles/medical_consultant/.env
/home/hermes/.hermes/profiles/medical_consultant/auth.json
/home/hermes/.hermes/.env
/home/hermes/.hermes/auth.json
```
