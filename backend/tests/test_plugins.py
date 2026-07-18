from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
async def plugin_service(tmp_path: Path):
    from big_bear_ai.database import Database
    from big_bear_ai.services.plugins import PluginService

    database = Database(tmp_path / "big-bear.db")
    await database.initialize()
    return PluginService(database)


@pytest.mark.asyncio
async def test_plugin_install_disable_enable_and_uninstall(plugin_service) -> None:
    from big_bear_ai.services.plugins import PluginError

    catalogue = await plugin_service.list()
    assert [item["id"] for item in catalogue["items"]] == [
        "api-validator",
        "data-generator",
        "log-analyzer",
    ]
    assert all(item["installed"] is False for item in catalogue["items"])

    installed = await plugin_service.install("api-validator")
    assert installed["installed"] is True
    assert installed["enabled"] is True
    assert installed["configuration"] == {}

    valid = await plugin_service.call(
        "api-validator",
        {
            "instance": {"id": 1},
            "schema": {
                "type": "object",
                "required": ["id"],
                "properties": {"id": {"type": "integer"}},
            },
        },
    )
    assert valid == {"valid": True, "errors": []}

    await plugin_service.set_enabled("api-validator", False)
    with pytest.raises(PluginError) as disabled:
        await plugin_service.call(
            "api-validator",
            {"instance": {"id": 1}, "schema": {"type": "object"}},
        )
    assert disabled.value.code == "PLUGIN_DISABLED"

    await plugin_service.set_enabled("api-validator", True)
    await plugin_service.uninstall("api-validator")
    with pytest.raises(PluginError) as missing:
        await plugin_service.call(
            "api-validator",
            {"instance": {"id": 1}, "schema": {"type": "object"}},
        )
    assert missing.value.code == "PLUGIN_NOT_INSTALLED"


@pytest.mark.asyncio
async def test_data_generator_is_bounded_and_deterministic(plugin_service) -> None:
    await plugin_service.install("data-generator")

    generated = await plugin_service.call(
        "data-generator",
        {
            "count": 2,
            "schema": {
                "name": "string",
                "attempt": "integer",
                "score": "number",
                "active": "boolean",
            },
        },
    )

    assert generated == [
        {"name": "sample-1", "attempt": 1, "score": 1.0, "active": True},
        {"name": "sample-2", "attempt": 2, "score": 2.0, "active": False},
    ]

    from big_bear_ai.services.plugins import PluginError

    with pytest.raises(PluginError, match="count"):
        await plugin_service.call(
            "data-generator", {"count": 101, "schema": {"id": "integer"}}
        )


@pytest.mark.asyncio
async def test_api_validator_returns_structured_errors(plugin_service) -> None:
    await plugin_service.install("api-validator")

    valid = await plugin_service.call(
        "api-validator",
        {
            "instance": {"id": 1},
            "schema": {
                "type": "object",
                "required": ["id"],
                "properties": {"id": {"type": "integer"}},
            },
        },
    )
    invalid = await plugin_service.call(
        "api-validator",
        {
            "instance": {"id": "wrong"},
            "schema": {"properties": {"id": {"type": "integer"}}},
        },
    )

    assert valid == {"valid": True, "errors": []}
    assert invalid["valid"] is False
    assert invalid["errors"][0]["path"] == ["id"]


@pytest.mark.asyncio
async def test_log_analyzer_filters_and_summarizes(plugin_service) -> None:
    await plugin_service.install("log-analyzer")

    result = await plugin_service.call(
        "log-analyzer",
        {
            "text": "INFO booted\nERROR checkout failed\nWARN slow\nERROR payment failed",
            "level": "ERROR",
            "contains": "failed",
        },
    )

    assert result["count"] == 2
    assert result["levels"] == {"ERROR": 2}
    assert result["lines"] == ["ERROR checkout failed", "ERROR payment failed"]


@pytest.mark.asyncio
async def test_unknown_plugin_is_rejected(plugin_service) -> None:
    from big_bear_ai.services.plugins import PluginError

    with pytest.raises(PluginError) as error:
        await plugin_service.install("remote-package")
    assert error.value.code == "PLUGIN_NOT_FOUND"


@pytest.mark.asyncio
async def test_management_graph_exposes_plugin_workflow(tmp_path: Path) -> None:
    from big_bear_ai.config import load_settings
    from big_bear_ai.graphs.management import build_management_graph

    graph = build_management_graph(
        load_settings(
            {"BIG_BEAR_DATA_DIR": str(tmp_path), "LANGSMITH_TRACING": "false"}
        )
    )
    installed = await graph.ainvoke(
        {
            "operation": "action",
            "resource": "plugin",
            "payload": {"action": "install", "plugin_id": "data-generator"},
        }
    )
    assert installed["ok"] is True

    called = await graph.ainvoke(
        {
            "operation": "action",
            "resource": "plugin",
            "payload": {
                "action": "call",
                "plugin_id": "data-generator",
                "input": {
                    "count": 2,
                    "schema": {"name": "string", "attempt": "integer"},
                },
            },
        }
    )
    assert called["data"] == [
        {"name": "sample-1", "attempt": 1},
        {"name": "sample-2", "attempt": 2},
    ]
