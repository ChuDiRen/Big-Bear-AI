from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
async def repository(tmp_path: Path):
    from big_bear_ai.database import Database
    from big_bear_ai.repositories.resources import ResourceRepository

    database = Database(tmp_path / "big-bear.db")
    await database.initialize()
    return ResourceRepository(database)


@pytest.mark.asyncio
async def test_project_crud_search_and_pagination(repository) -> None:
    first = await repository.create(
        "project", {"name": "Checkout API", "description": "Payment regression"}
    )
    second = await repository.create(
        "project", {"name": "Mobile UI", "description": "Checkout screens"}
    )

    page = await repository.list("project", search="checkout", limit=1)

    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert page["next_cursor"] == "1"

    next_page = await repository.list(
        "project", search="checkout", limit=1, cursor=page["next_cursor"]
    )
    assert {page["items"][0]["id"], next_page["items"][0]["id"]} == {
        first["id"],
        second["id"],
    }

    updated = await repository.update(
        "project", first["id"], {"status": "active", "description": "Updated"}
    )
    assert updated["status"] == "active"
    assert updated["description"] == "Updated"

    await repository.delete("project", first["id"])
    assert await repository.get("project", first["id"]) is None


@pytest.mark.asyncio
async def test_design_requires_project_and_cascades_on_delete(repository) -> None:
    project = await repository.create("project", {"name": "Web", "description": ""})
    design = await repository.create(
        "design",
        {
            "project_id": project["id"],
            "title": "Login coverage",
            "content": "Cover valid and invalid credentials",
        },
    )

    with pytest.raises(sqlite3.IntegrityError):
        await repository.create(
            "design",
            {"project_id": "missing", "title": "Invalid", "content": ""},
        )

    await repository.delete("project", project["id"])
    assert await repository.get("design", design["id"]) is None


@pytest.mark.asyncio
async def test_read_only_resources_are_enforced(repository) -> None:
    from big_bear_ai.repositories.resources import ReadOnlyResourceError

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

    await repository.database.run(insert_read_only_rule)
    official_rule = await repository.get("rule", "read-only-rule")

    assert official_rule["read_only"] is True
    with pytest.raises(ReadOnlyResourceError):
        await repository.update(
            "rule", official_rule["id"], {"description": "tampered"}
        )
    with pytest.raises(ReadOnlyResourceError):
        await repository.delete("rule", official_rule["id"])


@pytest.mark.asyncio
async def test_json_fields_round_trip_for_writable_catalogues(repository) -> None:
    rule = await repository.create(
        "rule",
        {
            "title": "Contract checks",
            "description": "Validate response bodies",
            "definition": "Every response must match its schema.",
            "tags": ["API", "schema"],
            "enabled": True,
        },
    )
    prompt = await repository.create(
        "prompt",
        {
            "title": "Generate cases",
            "description": "Generate boundary cases",
            "template": "Generate tests for {target}",
            "variables": ["target"],
            "tags": ["testing"],
        },
    )
    agent = await repository.create(
        "agent",
        {
            "name": "API specialist",
            "description": "Designs API tests",
            "instructions": "Focus on contracts and negative paths.",
            "allowed_rule_ids": [rule["id"]],
            "allowed_plugin_ids": [],
            "allowed_document_ids": [],
        },
    )

    assert rule["tags"] == ["API", "schema"]
    assert prompt["variables"] == ["target"]
    assert agent["allowed_rule_ids"] == [rule["id"]]
    assert rule["read_only"] is False


@pytest.mark.asyncio
async def test_repository_rejects_unknown_resources(repository) -> None:
    from big_bear_ai.repositories.resources import UnknownResourceError

    with pytest.raises(UnknownResourceError):
        await repository.list("users")
