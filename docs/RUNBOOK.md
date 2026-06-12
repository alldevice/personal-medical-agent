# MVP runbook: medical_consultant Hermes profile without Docker

## 0. Live decision

The MVP is a Hermes profile plus local vault and CLI tools. There is no standalone Docker container.

The live profile name is:

```text
medical_consultant
```

The live gateway service is:

```text
hermes-medical-consultant-gateway.service
```

Runtime shape:

```text
Telegram dedicated medical bot
  -> hermes-medical-consultant-gateway.service
  -> Hermes profile medical_consultant
  -> /srv/hermes-medical/repo/.venv/bin/medical-agent
  -> /srv/hermes-medical/data
```

## 1. Preconditions

- Server user `aiadmin` exists and has sudo.
- Server user `hermes` exists.
- Existing Hermes runtime works.
- Existing `kanban_operator` profile works.
- A second Telegram bot token has been created for `medical_consultant`.
- Do not add `hermes` to the Docker group.

## 2. Create vault directories

Run as `aiadmin`:

```bash
sudo install -d -m 755 -o root -g root /srv/hermes-medical
sudo install -d -m 750 -o hermes -g hermes /srv/hermes-medical/repo
sudo install -d -m 700 -o hermes -g hermes /srv/hermes-medical/data
sudo install -d -m 700 -o hermes -g hermes /srv/hermes-medical/config
sudo -u hermes -H mkdir -p \
  /srv/hermes-medical/data/raw \
  /srv/hermes-medical/data/extracted_text \
  /srv/hermes-medical/data/normalized \
  /srv/hermes-medical/data/timeline \
  /srv/hermes-medical/data/db \
  /srv/hermes-medical/data/audit \
  /srv/hermes-medical/data/backups
sudo chmod 700 /srv/hermes-medical/data
sudo find /srv/hermes-medical/data -type d -exec chmod 700 {} \;
sudo find /srv/hermes-medical/data -type f -exec chmod 600 {} \;
sudo chown -R hermes:hermes /srv/hermes-medical/data
```

## 3. Clone repository

Use SSH, not GitHub password authentication:

```bash
sudo -u hermes -H git clone git@github.com:alldevice/personal-medical-agent.git /srv/hermes-medical/repo
sudo -u hermes -H git -C /srv/hermes-medical/repo status --short
```

## 4. Create local medical config

```bash
sudo -u hermes -H cp /srv/hermes-medical/repo/config/.env.example /srv/hermes-medical/config/.env
sudo chmod 600 /srv/hermes-medical/config/.env
sudo -u hermes -H sed -i 's/^HERMES_MEDICAL_PROFILE=.*/HERMES_MEDICAL_PROFILE=medical_consultant/' /srv/hermes-medical/config/.env
```

This file is for vault settings. The dedicated Telegram bot token must be stored in the Hermes profile env:

```text
/home/hermes/.hermes/profiles/medical_consultant/.env
```

## 5. Create Python virtualenv

```bash
sudo -u hermes -H python3 -m venv /srv/hermes-medical/repo/.venv
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/python -m pip install --upgrade pip
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
```

## 6. Initialize SQLite vault

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
sudo -u hermes -H ls -la /srv/hermes-medical/data/db
```

Expected: `medical.sqlite` exists.

## 7. Manual ingest smoke test

Create and ingest a synthetic source file:

```bash
cd /
sudo -u hermes -H bash -lc 'echo "synthetic test document" > /tmp/medical-test.txt'
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent ingest \
  --file /tmp/medical-test.txt \
  --type "test-document" \
  --date "2026-06-12" \
  --comment "MVP smoke test"
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
sudo -u hermes -H rm -f /tmp/medical-test.txt
```

Materialize the fast-access working copy while preserving the raw original:

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent extract --all
sudo -u hermes -H find /srv/hermes-medical/data/extracted_text -maxdepth 3 -type f | sed -n '1,20p'
```

Build the source-linked search index from extracted working copies and timeline notes:

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent index --all
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent search "test document" --limit 5
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent summary "test document" --limit 5
```

Search output must show source document ids and snippets. Treat `summary` output as source-linked material only; medical interpretation must remain separate from document facts.

## 8. Create or refresh Hermes profile

The live profile path is:

```text
/home/hermes/.hermes/profiles/medical_consultant
```

Use `profiles/medical_consultant/PROFILE.md` as the source profile instruction. The live `SOUL.md` should contain the same safety and source-of-truth boundaries.

`medical_consultant` should use the same provider/auth style as `kanban_operator`, but not the same Telegram bot token.

## 9. Configure dedicated Telegram bot token

Create the dedicated bot in BotFather, then store its token only on the server. Do not paste the token into Git, docs, logs, or chat transcripts.

The profile env must be a real file, not a symlink to shared `.env`:

```text
/home/hermes/.hermes/profiles/medical_consultant/.env
```

It should contain:

```text
TELEGRAM_BOT_TOKEN=<medical bot token>
TELEGRAM_ALLOWED_USERS=<same allowed users policy as needed>
HERMES_MEDICAL_PROFILE=medical_consultant
```

## 10. Install systemd gateway

Service path:

```text
/etc/systemd/system/hermes-medical-consultant-gateway.service
```

Expected `ExecStart`:

```text
/home/hermes/.local/bin/hermes --profile medical_consultant gateway run
```

Expected working directory:

```text
/srv/hermes-medical/repo
```

The service should run as `hermes:hermes` and include the same proxy environment as `hermes-kanban-operator-gateway.service`.

## 11. Verify runtime

```bash
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
journalctl -u hermes-medical-consultant-gateway.service -n 120 --no-pager
sudo -u hermes -H bash -lc 'export HOME=/home/hermes; export PATH=/home/hermes/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; /home/hermes/.local/bin/hermes gateway list'
```

Expected:

```text
kanban_operator       running
medical_consultant    running
```

## 12. First Telegram check

Send to the dedicated medical bot:

```text
/start
```

Then:

```text
Привет. Кто ты и какой у тебя профиль?
```

Expected answer: the bot identifies itself as Hermes Agent profile `medical_consultant`.

If Telegram says no home channel is set, send:

```text
/sethome
```

## 12.1 Honcho conversational memory verification

Honcho is used only for conversational/context memory. It is not a medical source of truth.

Expected host-level config in `/home/hermes/.hermes/honcho.json`:

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

Verification commands:

```bash
curl -sS "http://127.0.0.1:8011/v3/workspaces/hermes_medical_consultant/peers/hermes_medical_consultant/card?target=human_sergei" | python3 -m json.tool

sudo docker exec -i honcho-hermes-postgres psql -U postgres -d postgres -c "
select peer_name, count(*) as messages, max(created_at) as last_msg
from public.messages
where workspace_name = 'hermes_medical_consultant'
  and created_at >= now() - interval '60 minutes'
group by peer_name
order by peer_name;
"
```

Expected after a Telegram smoke test: recent rows should use `human_sergei` and `hermes_medical_consultant`, not raw `237187787`.

Telegram smoke prompts:

```text
honcho_profile peer=user
```

```text
Скажи коротко: что ты помнишь обо мне из разговорной памяти, и является ли это медицинским источником правды?
```

## 13. Acceptance checklist

- `/home/hermes/.hermes/profiles/medical_consultant` exists.
- `/home/hermes/.hermes/profiles/medical_consultant/.env` is a real file with the dedicated bot token.
- `/home/hermes/.hermes/profiles/medical_consultant/auth.json` exists.
- `/srv/hermes-medical/data/db/medical.sqlite` exists.
- `medical-agent timeline --limit 5` works as `hermes`.
- `hermes gateway list` shows both `kanban_operator` and `medical_consultant` running.
- Telegram bot answers as `medical_consultant`.
- Honcho medical workspace uses `human_sergei` for the Telegram user alias and does not write new user messages as raw `237187787`.

## Telegram cache ingest

The Hermes Telegram gateway downloads supported inbound files to the profile cache. Import those cached files into the medical vault and search index with this command:

    sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent telegram-cache-ingest --once

Dry run:

    sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent telegram-cache-ingest --once --dry-run

Default scanned directories:

- /home/hermes/.hermes/profiles/medical_consultant/cache/documents
- /home/hermes/.hermes/profiles/medical_consultant/document_cache
- /home/hermes/.hermes/profiles/medical_consultant/cache/images
- /home/hermes/.hermes/profiles/medical_consultant/image_cache

This is intentionally a cache-to-vault adapter. The immutable source of truth remains /srv/hermes-medical/data/raw, and the Telegram cache may be cleaned by Hermes.

## Telegram cache ingest timer

The repository includes deployable systemd templates for a low-risk periodic scan:

```text
deploy/systemd/hermes-medical-telegram-cache-ingest.service
deploy/systemd/hermes-medical-telegram-cache-ingest.timer
```

This timer does not start another Telegram poller and does not patch Hermes gateway internals. It only runs the existing idempotent command:

```text
/srv/hermes-medical/repo/.venv/bin/medical-agent telegram-cache-ingest --once
```

Install and enable after reviewing the checked-out repository diff:

```bash
sudo install -m 0644 -o root -g root \
  /srv/hermes-medical/repo/deploy/systemd/hermes-medical-telegram-cache-ingest.service \
  /etc/systemd/system/hermes-medical-telegram-cache-ingest.service
sudo install -m 0644 -o root -g root \
  /srv/hermes-medical/repo/deploy/systemd/hermes-medical-telegram-cache-ingest.timer \
  /etc/systemd/system/hermes-medical-telegram-cache-ingest.timer
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-medical-telegram-cache-ingest.timer
```

Before the first live run or before changing timer behavior, take a SQLite backup:

```bash
sudo -u hermes -H mkdir -p /srv/hermes-medical/data/backups
sudo -u hermes -H cp -a \
  /srv/hermes-medical/data/db/medical.sqlite \
  /srv/hermes-medical/data/backups/medical.sqlite.before-telegram-cache-timer.$(date -u +%Y%m%dT%H%M%SZ)
```

Manual smoke check:

```bash
systemctl list-timers --all | grep hermes-medical-telegram-cache-ingest || true
sudo systemctl start hermes-medical-telegram-cache-ingest.service
sudo systemctl status hermes-medical-telegram-cache-ingest.service --no-pager -l
sudo journalctl -u hermes-medical-telegram-cache-ingest.service -n 80 --no-pager
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
```

Rollback/disable without deleting stored medical data:

```bash
sudo systemctl disable --now hermes-medical-telegram-cache-ingest.timer
sudo systemctl daemon-reload
```
