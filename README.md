# Personal Medical Agent for Hermes

Telegram-first personal medical archive and retrieval workflow implemented as a **Hermes profile + local vault + small CLI tools**.

This repository is the living runbook and codebase for the personal medical agent. The MVP does **not** run its own Docker container and does **not** run a separate Telegram bot. It uses the existing Hermes ecosystem and existing Hermes Telegram gateway/subscription credentials.

## Current MVP decision

Use the existing Linux user and runtime:

```text
existing Hermes runtime
  + profile: medical_agent
  + existing OpenAI subscription/OAuth/provider credentials
  + existing Telegram gateway

/srv/hermes-medical/
  repo/       # git clone of this repository
  data/       # real medical vault, never Git
  config/     # local settings, never Git
```

## MVP goals

- Add a separate Hermes profile named `medical_agent`.
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
  runs the medical CLI from the Hermes profile
```

Do not add `hermes` to the Docker group for this MVP.

## Quick start on the server

Run the full command block from [`docs/RUNBOOK.md`](docs/RUNBOOK.md). The short version is:

```bash
sudo install -d -m 755 -o root -g root /srv/hermes-medical
sudo install -d -m 750 -o hermes -g hermes /srv/hermes-medical/repo
sudo install -d -m 700 -o hermes -g hermes /srv/hermes-medical/data
sudo install -d -m 700 -o hermes -g hermes /srv/hermes-medical/config

sudo -u hermes -H git clone https://github.com/alldevice/personal-medical-agent.git /srv/hermes-medical/repo
sudo -u hermes -H python3 -m venv /srv/hermes-medical/repo/.venv
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
```

## First manual ingest test

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent ingest \
  --file /path/to/test.pdf \
  --type "EGD" \
  --date "2026-06-10" \
  --comment "stomach pain evaluation"

sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline
```

## Telegram/Hermes flow

The intended workflow is:

```text
Telegram message to existing Hermes gateway
  -> Hermes profile medical_agent
  -> local file saved into /srv/hermes-medical/data/raw
  -> medical-agent ingest
  -> SQLite + timeline update
  -> Telegram response from medical_agent
```

## Safety boundary

This system is a personal archive and assistant. It does not diagnose, prescribe, cancel medication, or replace medical care. Answers must distinguish source facts from model interpretation.
