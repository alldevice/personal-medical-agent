# Operations guide

This document explains how to operate the live `medical_consultant` system on `ai-server`.

## Service status

Check the medical gateway:

```bash
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
journalctl -u hermes-medical-consultant-gateway.service -n 120 --no-pager
```

Check all Hermes gateways:

```bash
sudo -u hermes -H bash -lc 'export HOME=/home/hermes; export PATH=/home/hermes/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; /home/hermes/.local/bin/hermes gateway list'
```

Expected live state:

```text
kanban_operator       running
medical_consultant    running
```

## Start, stop, restart

```bash
sudo systemctl restart hermes-medical-consultant-gateway.service
sudo systemctl stop hermes-medical-consultant-gateway.service
sudo systemctl start hermes-medical-consultant-gateway.service
```

After restart:

```bash
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
journalctl -u hermes-medical-consultant-gateway.service -n 80 --no-pager
```

## Vault health check

```bash
cd /
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
sudo -u hermes -H ls -la /srv/hermes-medical/data/db
```

Expected:

```text
/srv/hermes-medical/data/db/medical.sqlite
```

## Recording patient self-reports

Use self-reports for clinically relevant patient-provided facts without an attached source document: medication actually taken, suspected allergies, symptom updates, home measurements, and uncertainty/corrections.

Rules:

- Keep them separate from clinician-issued records by using document type `самоотчёт пациента: <topic>`.
- Prefix comments and timeline wording with `Со слов пациента:`.
- Preserve uncertainty verbatim: do not turn `скорее всего Моксиклав` into a confirmed allergy.
- If a newer self-report corrects an older one, ingest the correction and soften the older timeline wording.

Example:

```bash
cat > /tmp/2026-06-12_patient_report_allergy_update.md <<'EOF'
# Самоотчёт пациента: аллергологический анамнез

Дата сообщения: 2026-06-12
Источник: Telegram

Со слов пациента: вероятная аллергическая реакция на Моксиклав в анамнезе; точный антибиотик не подтверждён. Также аллергия на пыльцу берёзы / поллиноз, обычно апрель–май.
EOF

sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent ingest \
  --file /tmp/2026-06-12_patient_report_allergy_update.md \
  --type 'самоотчёт пациента: аллергологический анамнез' \
  --date '2026-06-12' \
  --comment 'Со слов пациента: вероятная аллергия на Моксиклав в анамнезе, точный антибиотик не подтверждён; аллергия на пыльцу берёзы/поллиноз ежегодно апрель–май.'
```

## Manual ingest test

Use only synthetic or intentionally selected files.

```bash
cd /
sudo -u hermes -H bash -lc 'echo "synthetic test document" > /tmp/medical-test.txt'
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent ingest \
  --file /tmp/medical-test.txt \
  --type "test-document" \
  --date "2026-06-12" \
  --comment "manual operations smoke test"
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent timeline --limit 5
sudo -u hermes -H rm -f /tmp/medical-test.txt
```

## Permissions check

```bash
cd /
sudo find /srv/hermes-medical -maxdepth 3 -printf '%M %u:%g %p\n' | sort | sed -n '1,200p'
sudo -u hermes -H test -r /srv/hermes-medical/data/db/medical.sqlite && echo OK_db_readable_by_hermes
```

Recommended:

```text
/srv/hermes-medical/data        hermes:hermes 700
/srv/hermes-medical/config      hermes:hermes 700
/srv/hermes-medical/data files  hermes:hermes 600
```

## Secret handling

Never print raw values of:

```text
TELEGRAM_BOT_TOKEN
OPENROUTER_API_KEY
OPENCODE_GO_API_KEY
XIAOMI_API_KEY
any API key or OAuth token
```

To check secret variable presence without values:

```bash
sudo -u hermes -H bash -lc 'grep -E "^(TELEGRAM_BOT_TOKEN|TELEGRAM_ALLOWED_USERS|HERMES_MEDICAL_PROFILE)=" ~/.hermes/profiles/medical_consultant/.env | sed -E "s/^(TELEGRAM_BOT_TOKEN=).*/\1<masked>/; s/^(TELEGRAM_ALLOWED_USERS=).*/\1<masked>/"'
```

## Telegram home channel

If the bot says no home channel is set, send this in the dedicated medical Telegram chat:

```text
/sethome
```

## Updating the running code from GitHub

Normal safe update from `main`:

```bash
cd /
sudo -u hermes -H git -C /srv/hermes-medical/repo status --short
sudo -u hermes -H git -C /srv/hermes-medical/repo pull --ff-only
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
sudo systemctl restart hermes-medical-consultant-gateway.service
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
```

Do not run `git commit` from the server unless the change is emergency-only and then immediately push it to a branch and open a PR.

## Local files that must not be committed

```text
/srv/hermes-medical/data/**
/srv/hermes-medical/config/.env
/home/hermes/.hermes/profiles/medical_consultant/.env
/home/hermes/.hermes/profiles/medical_consultant/auth.json
/home/hermes/.hermes/auth.json
/home/hermes/.hermes/.env
```

## Troubleshooting

### Gateway running but Telegram does not answer

```bash
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
journalctl -u hermes-medical-consultant-gateway.service -n 200 --no-pager
sudo -u hermes -H bash -lc 'export HOME=/home/hermes; export PATH=/home/hermes/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; /home/hermes/.local/bin/hermes --profile medical_consultant status'
```

Check that `TELEGRAM_BOT_TOKEN` exists in the profile `.env` and is not the same token as `kanban_operator`.

### SQLite or vault permission problems

```bash
sudo chown -R hermes:hermes /srv/hermes-medical/data /srv/hermes-medical/config
sudo find /srv/hermes-medical/data -type d -exec chmod 700 {} \;
sudo find /srv/hermes-medical/data -type f -exec chmod 600 {} \;
sudo chmod 700 /srv/hermes-medical/config
sudo find /srv/hermes-medical/config -type f -exec chmod 600 {} \;
```

### Git pull fails

Use SSH remote:

```bash
sudo -u hermes -H git -C /srv/hermes-medical/repo remote -v
sudo -u hermes -H git -C /srv/hermes-medical/repo remote set-url origin git@github.com:alldevice/personal-medical-agent.git
sudo -u hermes -H ssh -T git@github.com
```

## Backup notes

Minimum backup target:

```text
/srv/hermes-medical/data
/srv/hermes-medical/config
/home/hermes/.hermes/profiles/medical_consultant/SOUL.md
/home/hermes/.hermes/profiles/medical_consultant/profile.yaml
```

Do not push backups with real medical data or secrets into GitHub.
