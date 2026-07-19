from __future__ import annotations

import sqlite3

import pytest

from big_bear_ai.auth import service


def configure_inmem_auth(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("BIG_BEAR_RUNTIME", "inmem")
    monkeypatch.setenv("AUTH_DEV_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_AUDIENCE", "big-bear-test")
    monkeypatch.setattr(service, "SQLITE_PATH", tmp_path / "auth.db")


def test_inmem_auth_registers_users_and_issues_verifiable_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    configure_inmem_auth(monkeypatch, tmp_path)

    user = service.register_user(
        username="bear",
        email="bear@example.com",
        password="password-123",
        display_name=None,
    )
    token = service.issue_token(user)

    assert service.verify_token(f"Bearer {token}")["sub"] == user["id"]
    assert service.authenticate_user("bear", "password-123")["email"] == "bear@example.com"


def test_inmem_auth_rejects_duplicate_users_and_invalid_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    configure_inmem_auth(monkeypatch, tmp_path)
    service.register_user("bear", "bear@example.com", "password-123", None)

    with pytest.raises(ValueError, match="already registered"):
        service.register_user("bear", "other@example.com", "password-123", None)
    with pytest.raises(ValueError, match="Invalid or expired"):
        service.verify_token("Bearer invalid")


def test_inmem_auth_uses_a_separate_sqlite_user_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    configure_inmem_auth(monkeypatch, tmp_path)
    service.register_user("bear", "bear@example.com", "password-123", None)

    with sqlite3.connect(service.SQLITE_PATH) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1