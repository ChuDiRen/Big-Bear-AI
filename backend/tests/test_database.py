from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_initialize_enables_wal_foreign_keys_and_creates_all_tables(
    tmp_path: Path,
) -> None:
    from big_bear_ai.database import Database

    database = Database(tmp_path / "big-bear.db")
    await database.initialize()

    def inspect(connection: sqlite3.Connection) -> tuple[str, int, set[str]]:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        return journal_mode, foreign_keys, tables

    journal_mode, foreign_keys, tables = await database.run(inspect)

    assert journal_mode == "wal"
    assert foreign_keys == 1
    assert {
        "schema_migrations",
        "projects",
        "test_designs",
        "rules",
        "prompts",
        "agent_profiles",
        "documents",
        "document_chunks",
        "mcp_servers",
        "plugin_catalogue",
        "plugin_installations",
    } <= tables


@pytest.mark.asyncio
async def test_initialize_starts_with_empty_user_content_and_real_plugin_catalogue(
    tmp_path: Path,
) -> None:
    from big_bear_ai.database import Database

    database = Database(tmp_path / "big-bear.db")

    await database.initialize()
    await database.initialize()

    def counts(connection: sqlite3.Connection) -> tuple[dict[str, int], set[str]]:
        table_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "rules",
                "prompts",
                "agent_profiles",
                "documents",
                "document_chunks",
                "mcp_servers",
                "plugin_catalogue",
            )
        }
        plugin_ids = {
            row[0]
            for row in connection.execute(
                "SELECT id FROM plugin_catalogue ORDER BY id"
            ).fetchall()
        }
        return table_counts, plugin_ids

    table_counts, plugin_ids = await database.run(counts)
    assert table_counts == {
        "rules": 0,
        "prompts": 0,
        "agent_profiles": 0,
        "documents": 0,
        "document_chunks": 0,
        "mcp_servers": 0,
        "plugin_catalogue": 3,
    }
    assert plugin_ids == {"api-validator", "data-generator", "log-analyzer"}


@pytest.mark.asyncio
async def test_initialize_removes_retired_builtin_plugins_from_existing_database(
    tmp_path: Path,
) -> None:
    from big_bear_ai.database import Database

    database = Database(tmp_path / "big-bear.db")
    await database.initialize()

    def seed_retired_plugin(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            INSERT INTO plugin_catalogue(
                id, name, description, category, icon, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "mock-server",
                "Mock Server",
                "Retired seeded mock plugin",
                "Mock",
                "server",
                "2025-10-01T00:00:00+00:00",
                "2025-10-01T00:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO plugin_installations(
                plugin_id, enabled, configuration, installed_at, updated_at
            ) VALUES (?, 1, '{}', ?, ?)
            """,
            (
                "mock-server",
                "2025-10-01T00:00:00+00:00",
                "2025-10-01T00:00:00+00:00",
            ),
        )

    await database.run(seed_retired_plugin)
    await database.initialize()

    def plugin_ids(connection: sqlite3.Connection) -> set[str]:
        return {
            row[0]
            for row in connection.execute(
                "SELECT id FROM plugin_catalogue ORDER BY id"
            ).fetchall()
        }

    assert await database.run(plugin_ids) == {
        "api-validator",
        "data-generator",
        "log-analyzer",
    }


@pytest.mark.asyncio
async def test_run_closes_connection_after_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from big_bear_ai.database import Database

    database = Database(tmp_path / "big-bear.db")
    connections: list[sqlite3.Connection] = []

    def tracked_connect() -> sqlite3.Connection:
        connection = sqlite3.connect(database.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connections.append(connection)
        return connection

    monkeypatch.setattr(database, "_connect", tracked_connect)
    await database.run(lambda connection: connection.execute("SELECT 1").fetchone()[0])

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
