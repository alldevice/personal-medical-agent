from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE = REPO_ROOT / "deploy" / "systemd" / "hermes-medical-telegram-cache-ingest.service"
TIMER = REPO_ROOT / "deploy" / "systemd" / "hermes-medical-telegram-cache-ingest.timer"


def test_telegram_cache_ingest_service_runs_existing_cli_once() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "Type=oneshot" in text
    assert "User=hermes" in text
    assert "Group=hermes" in text
    assert "WorkingDirectory=/srv/hermes-medical/repo" in text
    assert "EnvironmentFile=-/home/hermes/.hermes/profiles/medical_consultant/.env" in text
    assert "HERMES_MEDICAL_TELEGRAM_REPLY_ENABLED=1" in text
    assert (
        "ExecStart=/srv/hermes-medical/repo/.venv/bin/medical-agent "
        "telegram-cache-ingest --once"
    ) in text
    assert "gateway run" not in text


def test_telegram_cache_ingest_timer_targets_service() -> None:
    text = TIMER.read_text(encoding="utf-8")

    assert "OnBootSec=2min" in text
    assert "OnUnitActiveSec=2min" in text
    assert "Persistent=true" in text
    assert "Unit=hermes-medical-telegram-cache-ingest.service" in text
    assert "WantedBy=timers.target" in text
