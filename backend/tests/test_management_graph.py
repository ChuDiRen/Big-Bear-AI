from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
async def management_graph(tmp_path: Path):
    from big_bear_ai.config import load_settings
    from big_bear_ai.database import Database
    from big_bear_ai.graphs.management import build_management_graph

    settings = load_settings(
        {
            "BIG_BEAR_DATA_DIR": str(tmp_path),
            "LANGSMITH_TRACING": "false",
        }
    )
    database = Database(settings.database_path)
    await database.initialize()
    graph = build_management_graph(settings)
    return graph, database


@pytest.mark.asyncio
async def test_management_graph_runs_resource_crud(management_graph) -> None:
    graph, _database = management_graph
    created = await graph.ainvoke(
        {
            "operation": "create",
            "resource": "project",
            "payload": {"name": "Checkout", "description": "API regression"},
        }
    )
    assert created["ok"] is True
    assert created["data"]["name"] == "Checkout"
    project_id = created["data"]["id"]

    listed = await graph.ainvoke(
        {
            "operation": "list",
            "resource": "project",
            "query": {"search": "check", "limit": 10},
        }
    )
    assert listed["ok"] is True
    assert listed["data"]["total"] == 1
    assert listed["data"]["items"][0]["id"] == project_id

    updated = await graph.ainvoke(
        {
            "operation": "update",
            "resource": "project",
            "resource_id": project_id,
            "payload": {"status": "active"},
        }
    )
    assert updated["ok"] is True
    assert updated["data"]["status"] == "active"

    deleted = await graph.ainvoke(
        {
            "operation": "delete",
            "resource": "project",
            "resource_id": project_id,
        }
    )
    assert deleted == {
        **deleted,
        "ok": True,
        "data": {"id": project_id, "deleted": True},
        "error": None,
    }

    missing = await graph.ainvoke(
        {"operation": "get", "resource": "project", "resource_id": project_id}
    )
    assert missing["ok"] is False
    assert missing["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_management_graph_returns_stable_validation_errors(
    management_graph,
) -> None:
    graph, _database = management_graph
    cases = [
        ({"operation": "explode", "resource": "project"}, "operation"),
        ({"operation": "list", "resource": "users"}, "resource"),
        ({"operation": "get", "resource": "project"}, "resource_id"),
        (
            {"operation": "create", "resource": "project", "payload": {}},
            "name",
        ),
    ]

    for request, expected_field in cases:
        result = await graph.ainvoke(request)
        assert result["ok"] is False
        assert result["data"] is None
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert expected_field in result["error"]["message"]


@pytest.mark.asyncio
async def test_management_graph_maps_read_only_errors(management_graph) -> None:
    graph, database = management_graph

    def insert_read_only_rule(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            INSERT INTO rules(
                id, title, description, definition, tags, author, official,
                enabled, read_only, created_at, updated_at
            ) VALUES (
                'read-only-rule', 'Official rule', '', 'Keep it immutable.', '[]', '系统', 1,
                1, 1, '2026-07-17T00:00:00+00:00', '2026-07-17T00:00:00+00:00'
            )
            """
        )

    await database.run(insert_read_only_rule)
    result = await graph.ainvoke(
        {
            "operation": "update",
            "resource": "rule",
            "resource_id": "read-only-rule",
            "payload": {"description": "changed"},
        }
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "READ_ONLY_RESOURCE"
    assert "read-only" in result["error"]["message"]
