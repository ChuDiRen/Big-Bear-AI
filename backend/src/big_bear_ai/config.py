from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_MODEL = "google_genai:gemini-2.5-flash"
DEFAULT_MAX_UPLOAD_MB = 10
DEFAULT_MCP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class Settings:
    model: str
    data_dir: Path
    database_path: Path
    uploads_dir: Path
    max_upload_bytes: int
    mcp_timeout_seconds: float
    langsmith_tracing: bool


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw = environment.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float(environment: Mapping[str, str], name: str, default: float) -> float:
    raw = environment.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def _boolean(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw = environment.get(name, str(default)).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def load_settings(environment: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environment is None else environment
    root = repository_root()
    configured_data_dir = Path(env.get("BIG_BEAR_DATA_DIR", "runtime"))
    data_dir = (
        configured_data_dir
        if configured_data_dir.is_absolute()
        else root / configured_data_dir
    ).resolve()
    max_upload_mb = _positive_int(
        env, "BIG_BEAR_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB
    )

    return Settings(
        model=env.get("BIG_BEAR_MODEL", DEFAULT_MODEL),
        data_dir=data_dir,
        database_path=data_dir / "big-bear.db",
        uploads_dir=data_dir / "uploads",
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        mcp_timeout_seconds=_positive_float(
            env, "BIG_BEAR_MCP_TIMEOUT_SECONDS", DEFAULT_MCP_TIMEOUT_SECONDS
        ),
        langsmith_tracing=_boolean(env, "LANGSMITH_TRACING", False),
    )

