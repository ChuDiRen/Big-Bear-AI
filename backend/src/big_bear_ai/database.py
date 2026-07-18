from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar


T = TypeVar("T")


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS test_designs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    source_thread_id TEXT,
    source_run_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    definition TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    author TEXT NOT NULL DEFAULT '用户',
    official INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    read_only INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    template TEXT NOT NULL,
    variables TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    author TEXT NOT NULL DEFAULT '用户',
    read_only INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '自定义',
    model_override TEXT,
    allowed_rule_ids TEXT NOT NULL DEFAULT '[]',
    allowed_plugin_ids TEXT NOT NULL DEFAULT '[]',
    allowed_document_ids TEXT NOT NULL DEFAULT '[]',
    author TEXT NOT NULL DEFAULT '用户',
    read_only INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    filename TEXT,
    media_type TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    extracted_text TEXT NOT NULL DEFAULT '',
    index_status TEXT NOT NULL DEFAULT 'ready',
    file_path TEXT,
    author TEXT NOT NULL DEFAULT '用户',
    read_only INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    content TEXT NOT NULL,
    UNIQUE(document_id, ordinal)
);

CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    content
);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    transport TEXT,
    public_config TEXT NOT NULL DEFAULT '{}',
    environment_refs TEXT NOT NULL DEFAULT '{}',
    desired_state TEXT NOT NULL DEFAULT 'disconnected',
    health_status TEXT NOT NULL DEFAULT 'Disconnected',
    last_error TEXT,
    icon TEXT NOT NULL DEFAULT 'plugs-connected',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plugin_catalogue (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    icon TEXT NOT NULL,
    config_schema TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plugin_installations (
    plugin_id TEXT PRIMARY KEY REFERENCES plugin_catalogue(id) ON DELETE CASCADE,
    enabled INTEGER NOT NULL DEFAULT 1,
    configuration TEXT NOT NULL DEFAULT '{}',
    installed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


BUILTIN_PLUGINS = (
    (
        "api-validator",
        "API Validator",
        "Validate JSON payloads against a JSON Schema contract.",
        "Validation",
        "shield-check",
    ),
    (
        "data-generator",
        "Data Generator",
        "Generate bounded structured test data from a simple field schema.",
        "Data",
        "database",
    ),
    (
        "log-analyzer",
        "Log Analyzer",
        "Filter and summarize plain-text logs for test investigation.",
        "Analysis",
        "magnifying-glass",
    ),
)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _run_sync(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        connection = self._connect()
        try:
            with connection:
                return operation(connection)
        finally:
            connection.close()

    async def run(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self._run_sync, operation)

    async def initialize(self) -> None:
        await self.run(_initialize)


def _initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (1, ?)",
        ("2026-07-17T00:00:00+00:00",),
    )
    _install_builtin_plugins(connection)


def _install_builtin_plugins(connection: sqlite3.Connection) -> None:
    created_at = "2025-11-01T00:00:00+00:00"
    builtin_ids = tuple(plugin[0] for plugin in BUILTIN_PLUGINS)
    placeholders = ", ".join("?" for _ in builtin_ids)
    connection.execute(
        f"DELETE FROM plugin_installations WHERE plugin_id NOT IN ({placeholders})",
        builtin_ids,
    )
    connection.execute(
        f"DELETE FROM plugin_catalogue WHERE id NOT IN ({placeholders})",
        builtin_ids,
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO plugin_catalogue(
            id, name, description, category, icon, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (identifier, name, description, category, icon, created_at, created_at)
            for identifier, name, description, category, icon in BUILTIN_PLUGINS
        ],
    )
