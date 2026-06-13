# LLM context

This file is the compact entry point for ChatGPT and other LLM agents that are asked to inspect, maintain, summarize, or continue work on this repository.

The public README is human-friendly and intentionally simplified. This file preserves the precise operational context needed for AI-assisted maintenance.

## Repository identity

```text
repository: alldevice/personal-medical-agent
default branch: main
system name: Personal Medical Agent
live profile: medical_consultant
primary runtime: Hermes profile + dedicated Telegram gateway + local vault + CLI tools
primary deployment: non-Docker MVP on an Ubuntu server
```

The repository is the source of truth for the personal medical consultant system: current live state, installation history, operations, change management, and roadmap.

## One-sentence system summary

A dedicated Hermes `medical_consultant` profile answers through a dedicated Telegram gateway and uses a local medical vault, SQLite database, extracted working copies, timeline entries, and source-linked search to help the user navigate their own medical archive.

## Current live shape

```text
Telegram dedicated medical bot
  -> systemd service: hermes-medical-consultant-gateway.service
  -> Hermes profile: medical_consultant
  -> medical vault CLI: /srv/hermes-medical/repo/.venv/bin/medical-agent
  -> local vault: /srv/hermes-medical/data
  -> SQLite: /srv/hermes-medical/data/db/medical.sqlite
```

There is no standalone Docker container in the current primary MVP path. Docker may be reintroduced later as optional packaging.

## Most important source-of-truth rule

Authoritative medical facts must come from one of these places:

```text
/srv/hermes-medical/data/raw
/srv/hermes-medical/data/extracted_text
/srv/hermes-medical/data/normalized
/srv/hermes-medical/data/timeline
/srv/hermes-medical/data/db/medical.sqlite
explicit current user messages
```

Honcho memory is used only for conversational continuity and preferences. It is not an authoritative store for raw medical records, lab values, diagnoses, prescriptions, medical images, or urgent safety decisions.

If a claim comes only from conversation memory, label it as conversation memory, not as document-confirmed medical fact.

## Read order for LLM agents

When asked to work with this repository, read these files in this order:

1. `README.md` — public overview and diagrams.
2. `docs/LLM_CONTEXT.md` — this compact LLM entry point.
3. `docs/CURRENT_SYSTEM.md` — live system source of truth.
4. `docs/ROADMAP.md` — detailed roadmap and status.
5. `docs/RUNBOOK.md` — installation and verification steps.
6. `docs/OPERATIONS.md` — operational commands and troubleshooting.
7. `docs/CHANGE_MANAGEMENT.md` — branch/PR/server update workflow.
8. `docs/ARCHITECTURE.md` — detailed architecture notes.
9. `docs/SAFETY_POLICY.md` — medical safety boundary.
10. `docs/DATA_MODEL.md` — current schema and data model notes.

Do not infer live behavior from README alone. Prefer `docs/CURRENT_SYSTEM.md` for the current runtime state.

## Functional capabilities already present

Current MVP capabilities include:

- dedicated Hermes profile `medical_consultant`;
- dedicated Telegram gateway service;
- local vault outside Git;
- SQLite database under the vault;
- `document_role` and `role_note` classification for document rows;
- deterministic CLI commands:
  - `medical-agent init`
  - `medical-agent ingest`
  - `medical-agent timeline`
  - `medical-agent extract`
  - `medical-agent index`
  - `medical-agent search`
  - `medical-agent summary`
  - `medical-agent telegram-cache-ingest --once`
- basic extracted working copy layer;
- basic text extraction/OCR hook;
- basic SQLite FTS over extracted text and timeline notes;
- Honcho conversational memory for preferences and continuity;
- periodic Telegram cache ingest with replies for newly imported attachments and first-seen duplicate-SHA cache files when reply environment is enabled.

## Roadmap compression

Use this as the compressed roadmap unless the user asks for detail:

```text
Done / live MVP:
  dedicated profile, dedicated Telegram gateway, local vault, SQLite, ingest,
  extracted working copies, basic text/OCR extraction, FTS search, Honcho memory.

Now:
  better caption parser, better Telegram attachment metadata,
  document listing/deletion workflow, backup and restore runbook.

Next:
  Telegram search/summary commands, timeline normalization,
  audit log, GitHub CI and secret checks.

Later:
  structured lab results, medication/allergy list, doctor visit preparation packets,
  optional Docker packaging, multi-user/caregiver mode, encryption-at-rest research.
```

## Change-management rule

Normal changes should use a branch and pull request.

Do not write directly to `main` unless the user explicitly asks for a direct commit or there is an emergency fix.

For docs-only changes, use a branch name like:

```text
docs/<short-topic>
```

For feature work, use:

```text
feature/<short-topic>
```

For operational changes, use:

```text
ops/<short-topic>
```

After a PR is merged, the server update flow is:

```bash
cd /
sudo -u hermes -H git -C /srv/hermes-medical/repo status --short
sudo -u hermes -H git -C /srv/hermes-medical/repo pull --ff-only
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
sudo systemctl restart hermes-medical-consultant-gateway.service
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
```

## Safety behavior for medical answers

When this repository is used to support a medical assistant, the assistant must:

- distinguish source facts from interpretation;
- avoid diagnosing;
- avoid prescribing;
- avoid telling the user to start, stop, or change medication without a clinician;
- surface uncertainty;
- recommend urgent care for red-flag symptoms;
- preserve traceability to source documents whenever possible;
- avoid treating OCR output as certain when quality is unknown.

## Public-release caution

Before the repository is made public, audit for:

- real medical data;
- Telegram tokens;
- provider/API credentials;
- OAuth state files;
- private logs;
- accidental screenshots;
- private hostnames or security-sensitive deployment details;
- any generated file under `/srv/hermes-medical/data` or profile credential paths.

## Never commit

```text
/srv/hermes-medical/data/**
/srv/hermes-medical/config/.env
/home/hermes/.hermes/profiles/medical_consultant/.env
/home/hermes/.hermes/profiles/medical_consultant/auth.json
/home/hermes/.hermes/.env
/home/hermes/.hermes/auth.json
```
