# Hermes Medical Agent MVP

Telegram-first personal medical archive and retrieval agent for Hermes.

This repository contains only code, schemas, prompts, Docker configuration, and synthetic examples. Real medical data must live outside Git, mounted as a local Docker volume.

## MVP goals

- Receive PDFs/images via Telegram bot.
- Store original files in a local `data/raw/` vault.
- Calculate SHA-256 for each original file.
- Extract text where possible.
- Create SQLite records for documents and timeline events.
- Provide Telegram queries over the local medical timeline.
- Keep Hermes/OpenAI/Telegram credentials in local config, not in Git.

## Local layout

Recommended server path:

```text
/srv/hermes-medical/
  repo/                 # git clone of this repository
  data/                 # real medical data, not Git
  config/               # local .env and policy files, not Git
```

## Start

```bash
cp config/.env.example config/.env
chmod 600 config/.env
mkdir -p data/raw data/extracted_text data/normalized data/timeline data/db data/audit data/backups
chmod 700 data config

docker compose up -d --build
```

## Telegram flow

Send a PDF/photo with a caption such as:

```text
type: EGD
date: 2026-06-10
comment: stomach pain evaluation
```

The bot stores the original file, extracts metadata, writes SQLite rows, and returns a short confirmation.

## Safety boundary

This system is a personal archive and assistant. It does not diagnose, prescribe, cancel medication, or replace medical care. Answers must distinguish source facts from model interpretation.
