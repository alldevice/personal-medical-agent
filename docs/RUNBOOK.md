# MVP runbook: Hermes medical profile without Docker

## 0. Decision

The MVP is a Hermes profile plus local vault and CLI tools. There is no standalone Docker container and no separate Telegram bot in the primary path.

```text
existing Hermes Telegram gateway
  -> Hermes profile medical_agent
  -> /srv/hermes-medical/repo/.venv/bin/medical-agent
  -> /srv/hermes-medical/data
```

## 1. Preconditions

- Server user `aiadmin` exists and has sudo.
- Server user `hermes` exists.
- Existing Hermes runtime and Telegram gateway already work.
- Existing Hermes OpenAI subscription/OAuth/provider credentials already work.
- Do not add `hermes` to the Docker group.

## 2. Create directories

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
```

## 3. Clone repository

Run as `aiadmin`:

```bash
sudo -u hermes -H git clone https://github.com/alldevice/personal-medical-agent.git /srv/hermes-medical/repo
sudo -u hermes -H git -C /srv/hermes-medical/repo status --short
```

Expected: clean working tree.

## 4. Create local config

Run as `aiadmin`:

```bash
sudo -u hermes -H cp /srv/hermes-medical/repo/config/.env.example /srv/hermes-medical/config/.env
sudo chmod 600 /srv/hermes-medical/config/.env
sudo -u hermes -H sed -n '1,120p' /srv/hermes-medical/config/.env
```

The MVP does not need a Telegram bot token in this file because it uses the existing Hermes Telegram gateway.

## 5. Create Python virtualenv

Run as `aiadmin`:

```bash
sudo -u hermes -H python3 -m venv /srv/hermes-medical/repo/.venv
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/python -m pip install --upgrade pip
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
```

## 6. Initialize SQLite vault

Run as `aiadmin`:

```bash
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
sudo -u hermes -H ls -la /srv/hermes-medical/data/db
```

Expected: `medical.sqlite` exists.

## 7. Manual ingest smoke test

Create a temporary fake file and ingest it:

```bash
sudo -u hermes -H bash -lc 'echo "synthetic test document" > /tmp/medical-test.txt'

sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent ingest \
  --file /tmp/medical-test.txt \
  --type "test-document" \
  --date "2026-06-12" \
  --comment "MVP smoke test"

sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
```

Expected: timeline contains the test document.

Optional cleanup:

```bash
sudo -u hermes -H rm -f /tmp/medical-test.txt
```

## 8. Add Hermes profile

First discover the existing Hermes profile layout instead of guessing it:

```bash
sudo -u hermes -H bash -lc '
set -e
printf "=== hermes home ===\n"
pwd
printf "=== likely Hermes dirs ===\n"
find ~/.hermes -maxdepth 5 -type d 2>/dev/null | sort | sed -n "1,200p"
printf "=== profile/instruction files ===\n"
find ~/.hermes -maxdepth 7 \( -iname "*profile*" -o -iname "SOUL.md" -o -iname "*instruction*" -o -iname "*.md" \) -print 2>/dev/null | sort | sed -n "1,240p"
'
```

Then copy or reference `profiles/medical_agent/PROFILE.md` in the same layout used by the existing profiles.

Suggested profile name:

```text
medical_agent
```

Minimum profile instruction:

```text
Use /srv/hermes-medical/repo/.venv/bin/medical-agent as the local storage tool.
Store incoming medical attachments in the vault through `medical-agent ingest`.
Use `medical-agent timeline` before answering timeline/history questions.
```

If the profile path is unclear, paste the discovery output into the next operator session and decide the exact copy command from evidence.

## 9. First Telegram workflow

Send a medical file to the existing Hermes Telegram gateway and route it to `medical_agent`.

Caption example:

```text
type: EGD
date: 2026-06-10
comment: stomach pain evaluation
```

The profile should save the attachment locally, call `medical-agent ingest`, then answer with the document id, type, date and SHA-256 prefix.

## 10. Acceptance checklist

```bash
sudo test -d /srv/hermes-medical/repo && echo OK_repo
sudo test -d /srv/hermes-medical/data && echo OK_data
sudo test -f /srv/hermes-medical/data/db/medical.sqlite && echo OK_db
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
```

Acceptance:

- repository is cloned under `/srv/hermes-medical/repo`;
- real vault is outside Git under `/srv/hermes-medical/data`;
- config is outside Git under `/srv/hermes-medical/config`;
- CLI works as `hermes`;
- profile `medical_agent` can call the CLI.
