from __future__ import annotations

from pathlib import Path

import pytest


def test_load_settings_uses_repository_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from big_bear_ai.config import load_settings

    for name in (
        "BIG_BEAR_MODEL",
        "BIG_BEAR_DATA_DIR",
        "BIG_BEAR_MAX_UPLOAD_MB",
        "BIG_BEAR_MCP_TIMEOUT_SECONDS",
        "LANGSMITH_TRACING",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    repository_root = Path(__file__).resolve().parents[2]
    assert settings.model == "google_genai:gemini-2.5-flash"
    assert settings.data_dir == repository_root / "runtime"
    assert settings.database_path == repository_root / "runtime" / "big-bear.db"
    assert settings.uploads_dir == repository_root / "runtime" / "uploads"
    assert settings.max_upload_bytes == 10 * 1024 * 1024
    assert settings.mcp_timeout_seconds == 15.0
    assert settings.langsmith_tracing is False


def test_load_settings_honors_environment_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from big_bear_ai.config import load_settings

    monkeypatch.setenv("BIG_BEAR_MODEL", "google_genai:gemini-test")
    monkeypatch.setenv("BIG_BEAR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BIG_BEAR_MAX_UPLOAD_MB", "3")
    monkeypatch.setenv("BIG_BEAR_MCP_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    settings = load_settings()

    assert settings.model == "google_genai:gemini-test"
    assert settings.data_dir == (tmp_path / "data").resolve()
    assert settings.max_upload_bytes == 3 * 1024 * 1024
    assert settings.mcp_timeout_seconds == 2.5
    assert settings.langsmith_tracing is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("BIG_BEAR_MAX_UPLOAD_MB", "0"),
        ("BIG_BEAR_MAX_UPLOAD_MB", "not-a-number"),
        ("BIG_BEAR_MCP_TIMEOUT_SECONDS", "-1"),
        ("BIG_BEAR_MCP_TIMEOUT_SECONDS", "never"),
        ("LANGSMITH_TRACING", "sometimes"),
    ],
)
def test_load_settings_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    from big_bear_ai.config import load_settings

    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        load_settings()

