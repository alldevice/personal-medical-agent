# Honcho conversational memory integration

Status: live runtime integration, documented after server smoke tests.

This document describes the medical consultant Honcho memory contour. It intentionally does not contain secrets, tokens, medical data, database dumps, or full `.env` values.

## Purpose

Honcho is enabled for `medical_consultant` only as conversational/context memory.

It helps the Telegram medical consultant remember stable interaction preferences and workflow conventions across sessions.

Honcho is not the medical source of truth.

## Runtime identity

```text
workspace: hermes_medical_consultant
host key: hermes.medical_consultant
canonical Human peer: human_sergei
Telegram runtime alias: 237187787 -> human_sergei
agent peer: hermes_medical_consultant
pinPeerName: false
```

Historical note: early pre-alias rows may exist under raw peer `237187787`. Do not rewrite old Honcho SQL rows manually unless there is a separate migration plan covering derived documents and peer-card side effects.

## Source-of-truth boundary

Authoritative medical facts remain in:

```text
/srv/hermes-medical/data/raw
/srv/hermes-medical/data/db/medical.sqlite
/srv/hermes-medical/data/extracted
current explicit user messages
```

Honcho can store:

- stable communication preferences;
- language and answer-style preferences;
- workflow preferences;
- doctor-preparation style;
- conversation continuity notes.

Honcho must not store or be treated as authoritative for:

- raw medical documents;
- lab values;
- medical images;
- full clinical records;
- prescriptions or medication changes as confirmed facts;
- diagnoses;
- urgent safety decisions;
- long verbatim medical narratives.

If a medical claim is recalled only from Honcho, label it as conversation memory and not document-confirmed.

## Expected `honcho.json` host block

```json
{
  "hosts": {
    "hermes.medical_consultant": {
      "enabled": true,
      "aiPeer": "hermes_medical_consultant",
      "peerName": "human_sergei",
      "workspace": "hermes_medical_consultant",
      "pinPeerName": false,
      "userPeerAliases": {
        "237187787": "human_sergei"
      }
    }
  }
}
```

## Peer-card seed

The live peer-card for `human_sergei` should contain only non-medical conversational rules, for example:

```text
human_sergei is Sergei, the primary user of the personal medical consultant Telegram bot.
human_sergei prefers calm, concise, practical Russian answers, especially for medical questions.
For human_sergei, medical answers must clearly separate source facts, patient self-reports, and model interpretation.
Honcho memory in this medical workspace is conversational memory only; medical source-of-truth facts must be verified against the local vault, SQLite timeline, or current explicit user message.
If a medical claim is recalled only from conversation memory, mark it as conversation memory and not document-confirmed.
```

## Smoke checks

Check peer-card API:

```bash
curl -sS "http://127.0.0.1:8011/v3/workspaces/hermes_medical_consultant/peers/hermes_medical_consultant/card?target=human_sergei" | python3 -m json.tool
```

Check recent message peers:

```bash
sudo docker exec -i honcho-hermes-postgres psql -U postgres -d postgres -c "
select peer_name, count(*) as messages, max(created_at) as last_msg
from public.messages
where workspace_name = 'hermes_medical_consultant'
  and created_at >= now() - interval '60 minutes'
group by peer_name
order by peer_name;
"
```

Expected recent peers after alias repair:

```text
human_sergei
hermes_medical_consultant
```

Raw `237187787` should not appear in new recent user traffic.

Telegram smoke:

```text
honcho_profile peer=user
```

```text
Скажи коротко: что ты помнишь обо мне из разговорной памяти, и является ли это медицинским источником правды?
```

Expected answer: the assistant recalls conversational preferences and explicitly says that Honcho is not the medical source of truth.

## Repository synchronization note

Live runtime changes must be synchronized to:

- `profiles/medical_consultant/PROFILE.md`;
- `docs/CURRENT_SYSTEM.md`;
- `docs/RUNBOOK.md`;
- `docs/ARCHITECTURE.md`;
- `docs/ROADMAP.md`;
- this document.
