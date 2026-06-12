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

## 13. Acceptance checklist

- `/home/hermes/.hermes/profiles/medical_consultant` exists.
- `/home/hermes/.hermes/profiles/medical_consultant/.env` is a real file with the dedicated bot token.
- `/home/hermes/.hermes/profiles/medical_consultant/auth.json` exists.
- `/srv/hermes-medical/data/db/medical.sqlite` exists.
- `medical-agent timeline --limit 5` works as `hermes`.
- `hermes gateway list` shows both `kanban_operator` and `medical_consultant` running.
- Telegram bot answers as `medical_consultant`.
