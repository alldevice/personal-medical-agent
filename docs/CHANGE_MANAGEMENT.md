# Change management

This repository is the source of truth for the medical consultant system. All planned changes should be represented here before they are applied to the live server, unless there is an emergency fix.

## Branching model

Default branch:

```text
main
```

Use feature branches for changes:

```text
feature/<short-topic>
fix/<short-topic>
docs/<short-topic>
ops/<short-topic>
```

Examples:

```text
feature/telegram-attachment-ingest
feature/sqlite-fts-search
ops/backup-restore-runbook
docs/current-system-refresh
```

## Preferred workflow

1. Decide the change in conversation or issue.
2. Update docs first when architecture or operations change.
3. Implement code changes in a branch.
4. Run tests locally or in CI.
5. Open a pull request.
6. Review diff and operational risk.
7. Merge to `main`.
8. Pull to `/srv/hermes-medical/repo` on the server.
9. Restart only the required service.
10. Verify Telegram, gateway status, and vault CLI.

## Normal update flow from ChatGPT/GitHub connector

Use GitHub edits or local development to create a branch and PR. Do not put secrets or medical data in commits.

Suggested PR checklist:

```text
- [ ] No real medical data committed.
- [ ] No tokens, API keys, OAuth files, or Telegram credentials committed.
- [ ] README/docs updated if behavior changed.
- [ ] Runbook updated if deployment changed.
- [ ] Tests added or updated for code behavior.
- [ ] Server update command is clear.
- [ ] Rollback command is clear.
```

## Normal server deployment after merge

Run as `aiadmin`:

```bash
cd /
sudo -u hermes -H git -C /srv/hermes-medical/repo status --short
sudo -u hermes -H git -C /srv/hermes-medical/repo pull --ff-only
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/medical-agent init
sudo systemctl restart hermes-medical-consultant-gateway.service
systemctl status hermes-medical-consultant-gateway.service --no-pager -l
sudo -u hermes -H bash -lc 'export HOME=/home/hermes; export PATH=/home/hermes/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; /home/hermes/.local/bin/hermes gateway list'
```

## When a server-side commit is allowed

Server-side commits are not the normal workflow. They are allowed only for emergency fixes or when the server has the only reproducible state.

If a server-side change is made:

```bash
cd /srv/hermes-medical/repo
sudo -u hermes -H git status --short
sudo -u hermes -H git checkout -b fix/<short-topic>
sudo -u hermes -H git add <changed-files>
sudo -u hermes -H git commit -m "Fix <short topic>"
sudo -u hermes -H git push -u origin fix/<short-topic>
```

Then open a PR and merge through GitHub.

Never commit:

```text
/srv/hermes-medical/data/**
/srv/hermes-medical/config/.env
/home/hermes/.hermes/profiles/medical_consultant/.env
/home/hermes/.hermes/profiles/medical_consultant/auth.json
```

## Rollback

For code-only rollback:

```bash
cd /
sudo -u hermes -H git -C /srv/hermes-medical/repo log --oneline -10
sudo -u hermes -H git -C /srv/hermes-medical/repo checkout <known-good-commit>
sudo -u hermes -H /srv/hermes-medical/repo/.venv/bin/pip install -e /srv/hermes-medical/repo
sudo systemctl restart hermes-medical-consultant-gateway.service
```

After rollback, create an issue or PR explaining what failed.

For database rollback, do not improvise. Restore from a known backup of `/srv/hermes-medical/data/db/medical.sqlite` and keep the failed DB copy for inspection.

## Versioning notes

The package version in `pyproject.toml` is currently MVP-level. Before external distribution, introduce explicit versioning:

```text
0.1.x  local MVP
0.2.x  automated Telegram ingest
0.3.x  search/extraction MVP
0.4.x  memory integration
1.0.0  stable personal medical archive assistant
```

## Definition of done for future changes

A change is done only when:

- code is in GitHub;
- docs match the live behavior;
- server is updated from GitHub, not manually diverged;
- `medical-agent timeline --limit 5` works;
- `hermes gateway list` shows `medical_consultant` running;
- Telegram smoke test works;
- no secrets or real medical data are committed.
