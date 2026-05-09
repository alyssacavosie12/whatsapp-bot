from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def test_cleanup_main_records_retention_audit_event(monkeypatch: Any) -> None:
    import scripts.cleanup_inbox as cleanup

    audit_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(cleanup, "INBOX_DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(cleanup, "INBOX_RETENTION_DAYS", 14)
    monkeypatch.setattr(
        cleanup,
        "cleanup_expired_messages",
        lambda database_url, retention_days: 7,
    )

    def fake_record_audit_event(database_url: str, **kwargs: Any) -> None:
        audit_calls.append({"database_url": database_url, **kwargs})

    monkeypatch.setattr(cleanup, "record_audit_event", fake_record_audit_event)

    assert cleanup.main() == 0
    assert audit_calls == [
        {
            "database_url": "postgresql://x",
            "actor": "system:retention-cleanup",
            "actor_role": "system",
            "action": "retention_cleanup",
            "metadata": {
                "deleted_messages": 7,
                "retention_days": 14,
            },
        }
    ]


def test_cleanup_main_fails_without_database_url(monkeypatch: Any) -> None:
    import scripts.cleanup_inbox as cleanup

    monkeypatch.setattr(cleanup, "INBOX_DATABASE_URL", "")

    assert cleanup.main() == 1


def test_railway_cleanup_service_is_configured_as_cron() -> None:
    config = tomllib.loads(Path("railway.cleanup.toml").read_text(encoding="utf-8"))

    assert config["deploy"]["startCommand"] == "python -m scripts.cleanup_inbox"
    assert config["deploy"]["cronSchedule"] == "0 9 * * *"
    assert config["deploy"]["restartPolicyType"] == "ON_FAILURE"
    assert config["deploy"]["restartPolicyMaxRetries"] == 3
