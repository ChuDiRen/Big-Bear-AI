from __future__ import annotations

import json
import sqlite3
import sys
import textwrap
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
async def mcp_service(tmp_path: Path):
    from big_bear_ai.config import load_settings
    from big_bear_ai.database import Database
    from big_bear_ai.services.mcp import MCPService

    settings = load_settings(
        {
            "BIG_BEAR_DATA_DIR": str(tmp_path),
            "BIG_BEAR_MCP_TIMEOUT_SECONDS": "5",
            "LANGSMITH_TRACING": "false",
        }
    )
    database = Database(settings.database_path)
    await database.initialize()
    return MCPService(database, settings)


def write_stdio_server(tmp_path: Path) -> Path:
    script = tmp_path / "test_mcp_server.py"
    script.write_text(
        textwrap.dedent(
            """
            from mcp.server.fastmcp import FastMCP

            server = FastMCP("big-bear-test")

            @server.tool()
            def add(a: int, b: int) -> int:
                return a + b

            if __name__ == "__main__":
                server.run(transport="stdio")
            """
        ).strip(),
        encoding="utf-8",
    )
    return script


@pytest.mark.asyncio
async def test_real_stdio_connect_list_call_and_disconnect(
    mcp_service, tmp_path: Path
) -> None:
    from big_bear_ai.services.mcp import MCPError

    script = write_stdio_server(tmp_path)
    server = await mcp_service.create(
        {
            "name": "Calculator",
            "description": "Test calculator",
            "transport": "stdio",
            "configuration": {
                "command": sys.executable,
                "args": [str(script)],
                "cwd": str(tmp_path),
            },
        }
    )

    connected = await mcp_service.connect(server["id"])
    assert connected["health_status"] == "Connected"
    assert connected["tools"][0]["name"] == "add"

    tools = await mcp_service.list_tools(server["id"])
    assert tools[0]["input_schema"]["required"] == ["a", "b"]

    result = await mcp_service.call_tool(server["id"], "add", {"a": 2, "b": 3})
    assert result["is_error"] is False
    assert result["structured_content"] == {"result": 5}

    disconnected = await mcp_service.disconnect(server["id"])
    assert disconnected["health_status"] == "Disconnected"
    with pytest.raises(MCPError) as error:
        await mcp_service.call_tool(server["id"], "add", {"a": 1, "b": 1})
    assert error.value.code == "MCP_NOT_CONNECTED"


@pytest.mark.asyncio
async def test_streamable_http_resolves_env_refs_without_persisting_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from big_bear_ai.config import load_settings
    from big_bear_ai.database import Database
    from big_bear_ai.services.mcp import MCPService

    captured: dict = {}

    class FakeSession:
        async def list_tools(self, cursor=None):
            return SimpleNamespace(
                tools=[SimpleNamespace(name="ping", description="Ping", inputSchema={})],
                nextCursor=None,
            )

    class FakeClient:
        def __init__(self, connections):
            captured.update(connections)

        @asynccontextmanager
        async def session(self, _server_name):
            yield FakeSession()

    monkeypatch.setenv("MCP_TEST_TOKEN", "super-secret-value")
    settings = load_settings(
        {"BIG_BEAR_DATA_DIR": str(tmp_path), "LANGSMITH_TRACING": "false"}
    )
    database = Database(settings.database_path)
    await database.initialize()
    service = MCPService(database, settings, client_factory=FakeClient)

    server = await service.create(
        {
            "name": "HTTP MCP",
            "transport": "streamable_http",
            "configuration": {
                "url": "http://127.0.0.1:8000/mcp",
                "headers": {"Authorization": "$env:MCP_TEST_TOKEN"},
            },
        }
    )
    connected = await service.connect(server["id"])

    assert captured[server["id"]]["transport"] == "streamable_http"
    assert captured[server["id"]]["headers"] == {
        "Authorization": "super-secret-value"
    }
    assert "super-secret-value" not in json.dumps(connected)

    def serialized_row(connection: sqlite3.Connection) -> str:
        row = connection.execute(
            "SELECT public_config, environment_refs FROM mcp_servers WHERE id = ?",
            (server["id"],),
        ).fetchone()
        return json.dumps(dict(row))

    assert "super-secret-value" not in await database.run(serialized_row)


@pytest.mark.asyncio
async def test_literal_secrets_and_unknown_env_refs_are_rejected(
    mcp_service, monkeypatch: pytest.MonkeyPatch
) -> None:
    from big_bear_ai.services.mcp import MCPError

    with pytest.raises(MCPError) as literal:
        await mcp_service.create(
            {
                "name": "Unsafe",
                "transport": "streamable_http",
                "configuration": {
                    "url": "http://localhost/mcp",
                    "headers": {"Authorization": "literal-secret"},
                },
            }
        )
    assert literal.value.code == "VALIDATION_ERROR"

    monkeypatch.delenv("MISSING_MCP_TOKEN", raising=False)
    server = await mcp_service.create(
        {
            "name": "Missing ref",
            "transport": "streamable_http",
            "configuration": {
                "url": "http://localhost/mcp",
                "headers": {"Authorization": "$env:MISSING_MCP_TOKEN"},
            },
        }
    )
    with pytest.raises(MCPError) as missing:
        await mcp_service.connect(server["id"])
    assert missing.value.code == "MCP_CONFIGURATION_ERROR"


@pytest.mark.asyncio
async def test_failed_connection_records_error_state(mcp_service) -> None:
    from big_bear_ai.services.mcp import MCPError

    server = await mcp_service.create(
        {
            "name": "Broken",
            "transport": "stdio",
            "configuration": {"command": "definitely-missing-command", "args": []},
        }
    )

    with pytest.raises(MCPError) as error:
        await mcp_service.connect(server["id"])
    assert error.value.code == "MCP_CONNECTION_FAILED"

    stored = await mcp_service.get(server["id"])
    assert stored["health_status"] == "Error"
    assert stored["last_error"]


@pytest.mark.asyncio
async def test_management_graph_maps_tool_discovery_disconnect_to_error_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from big_bear_ai.config import load_settings
    from big_bear_ai.database import Database
    from big_bear_ai.graphs import management as management_module
    from big_bear_ai.services.management import ManagementService

    class FlakySession:
        calls = 0

        async def list_tools(self, cursor=None):
            type(self).calls += 1
            if type(self).calls > 1:
                raise OSError("server disconnected")
            return SimpleNamespace(
                tools=[SimpleNamespace(name="ping", description="Ping", inputSchema={})],
                nextCursor=None,
            )

    class FlakyClient:
        def __init__(self, _connections):
            pass

        @asynccontextmanager
        async def session(self, _server_name):
            yield FlakySession()

    settings = load_settings(
        {"BIG_BEAR_DATA_DIR": str(tmp_path), "LANGSMITH_TRACING": "false"}
    )
    service = ManagementService(Database(settings.database_path), settings)
    service.mcp.client_factory = FlakyClient
    monkeypatch.setattr(management_module, "ManagementService", lambda *_: service)
    graph = management_module.build_management_graph(settings)
    created = await graph.ainvoke(
        {
            "operation": "create",
            "resource": "mcp",
            "payload": {
                "name": "Flaky server",
                "transport": "streamable_http",
                "configuration": {"url": "http://127.0.0.1:9/mcp"},
            },
        }
    )
    server_id = created["data"]["id"]
    connected = await graph.ainvoke(
        {
            "operation": "action",
            "resource": "mcp",
            "resource_id": server_id,
            "payload": {"action": "connect"},
        }
    )
    assert connected["ok"] is True

    try:
        result = await graph.ainvoke(
            {
                "operation": "action",
                "resource": "mcp",
                "resource_id": server_id,
                "payload": {"action": "list_tools"},
            }
        )
    except OSError as exc:
        pytest.fail(f"MCP error escaped the management envelope: {exc}")

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"]["code"] == "MCP_TOOL_DISCOVERY_FAILED"
    stored = await service.mcp.get(server_id)
    assert stored["health_status"] == "Error"


@pytest.mark.asyncio
async def test_management_graph_exposes_real_mcp_workflow(
    tmp_path: Path,
) -> None:
    from big_bear_ai.config import load_settings
    from big_bear_ai.graphs.management import build_management_graph

    script = write_stdio_server(tmp_path)
    graph = build_management_graph(
        load_settings(
            {
                "BIG_BEAR_DATA_DIR": str(tmp_path),
                "BIG_BEAR_MCP_TIMEOUT_SECONDS": "5",
                "LANGSMITH_TRACING": "false",
            }
        )
    )
    created = await graph.ainvoke(
        {
            "operation": "create",
            "resource": "mcp",
            "payload": {
                "name": "Calculator",
                "transport": "stdio",
                "configuration": {
                    "command": sys.executable,
                    "args": [str(script)],
                },
            },
        }
    )
    server_id = created["data"]["id"]

    connected = await graph.ainvoke(
        {
            "operation": "action",
            "resource": "mcp",
            "resource_id": server_id,
            "payload": {"action": "connect"},
        }
    )
    called = await graph.ainvoke(
        {
            "operation": "action",
            "resource": "mcp",
            "resource_id": server_id,
            "payload": {"action": "call", "tool_name": "add", "arguments": {"a": 4, "b": 6}},
        }
    )

    assert connected["ok"] is True
    assert called["data"]["structured_content"] == {"result": 10}
