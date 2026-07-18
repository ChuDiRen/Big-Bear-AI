from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import uuid4

from langchain_mcp_adapters.client import MultiServerMCPClient

from big_bear_ai.config import Settings
from big_bear_ai.database import Database


ENV_REFERENCE = re.compile(r"^\$env:([A-Za-z_][A-Za-z0-9_]*)$")


class MCPError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MCPService:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        client_factory: Callable[..., Any] = MultiServerMCPClient,
    ) -> None:
        self.database = database
        self.settings = settings
        self.client_factory = client_factory

    async def list(self, *, search: str = "") -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            parameters: list[Any] = []
            where = ""
            if search:
                where = " WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?"
                parameters = [f"%{search.lower()}%"] * 2
            rows = connection.execute(
                f"SELECT * FROM mcp_servers{where} ORDER BY updated_at DESC, id",
                parameters,
            ).fetchall()
            return {"items": [_decode_server(row) for row in rows], "total": len(rows)}

        return await self.database.run(operation)

    async def get(self, server_id: str) -> dict[str, Any] | None:
        def operation(connection: sqlite3.Connection) -> dict[str, Any] | None:
            row = connection.execute(
                "SELECT * FROM mcp_servers WHERE id = ?", (server_id,)
            ).fetchone()
            return _decode_server(row) if row else None

        return await self.database.run(operation)

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise MCPError("VALIDATION_ERROR", "name is required")
        transport, public_config, references = _validate_configuration(payload)
        identifier = str(uuid4())
        timestamp = _utc_now()

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            connection.execute(
                """
                INSERT INTO mcp_servers(
                    id, name, description, transport, public_config,
                    environment_refs, desired_state, health_status, icon,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'disconnected', 'Disconnected', ?, ?, ?)
                """,
                (
                    identifier,
                    name.strip(),
                    str(payload.get("description") or ""),
                    transport,
                    json.dumps(public_config, ensure_ascii=False),
                    json.dumps(references, ensure_ascii=False),
                    str(payload.get("icon") or "plugs-connected"),
                    timestamp,
                    timestamp,
                ),
            )
            return _get_required(connection, identifier)

        return await self.database.run(operation)

    async def configure(self, server_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        transport, public_config, references = _validate_configuration(payload)

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            current = _get_required(connection, server_id)
            connection.execute(
                """
                UPDATE mcp_servers
                SET name = ?, description = ?, transport = ?, public_config = ?,
                    environment_refs = ?, desired_state = 'disconnected',
                    health_status = 'Disconnected', last_error = NULL,
                    icon = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    str(payload.get("name") or current["name"]),
                    str(payload.get("description", current["description"])),
                    transport,
                    json.dumps(public_config, ensure_ascii=False),
                    json.dumps(references, ensure_ascii=False),
                    str(payload.get("icon") or current["icon"]),
                    _utc_now(),
                    server_id,
                ),
            )
            return _get_required(connection, server_id)

        return await self.database.run(operation)

    async def delete(self, server_id: str) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            _get_required(connection, server_id)
            connection.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))

        await self.database.run(operation)

    async def connect(self, server_id: str) -> dict[str, Any]:
        try:
            tools = await self._list_tools_from_server(server_id, require_connected=False)
        except MCPError as exc:
            await self._set_status(server_id, "connected", "Error", str(exc))
            raise
        except Exception as exc:
            await self._set_status(
                server_id,
                "connected",
                "Error",
                f"{type(exc).__name__}: connection failed",
            )
            raise MCPError("MCP_CONNECTION_FAILED", "MCP connection failed") from exc
        server = await self._set_status(server_id, "connected", "Connected", None)
        server["tools"] = tools
        return server

    async def disconnect(self, server_id: str) -> dict[str, Any]:
        return await self._set_status(server_id, "disconnected", "Disconnected", None)

    async def list_tools(self, server_id: str) -> list[dict[str, Any]]:
        return await self._list_tools_from_server(server_id, require_connected=True)

    async def call_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        server = await self._connected_server(server_id)
        if not isinstance(tool_name, str) or not tool_name:
            raise MCPError("VALIDATION_ERROR", "tool_name is required")
        if not isinstance(arguments, dict):
            raise MCPError("VALIDATION_ERROR", "arguments must be an object")
        try:
            client = self.client_factory({server_id: _connection_config(server)})
            async with asyncio.timeout(self.settings.mcp_timeout_seconds):
                async with client.session(server_id) as session:
                    result = await session.call_tool(tool_name, arguments)
        except MCPError:
            raise
        except TimeoutError as exc:
            raise MCPError("MCP_TIMEOUT", "MCP tool call timed out") from exc
        except Exception as exc:
            raise MCPError("MCP_TOOL_FAILED", "MCP tool call failed") from exc
        response = {
            "is_error": bool(result.isError),
            "structured_content": result.structuredContent,
            "content": [_serialize_content(item) for item in result.content],
        }
        if response["is_error"]:
            raise MCPError("MCP_TOOL_FAILED", "MCP tool returned an error")
        return response

    async def _list_tools_from_server(
        self, server_id: str, *, require_connected: bool
    ) -> list[dict[str, Any]]:
        server = (
            await self._connected_server(server_id)
            if require_connected
            else await self._required_server(server_id)
        )
        try:
            client = self.client_factory({server_id: _connection_config(server)})
            async with asyncio.timeout(self.settings.mcp_timeout_seconds):
                async with client.session(server_id) as session:
                    tools: list[dict[str, Any]] = []
                    cursor = None
                    while True:
                        page = await session.list_tools(cursor=cursor)
                        tools.extend(
                            {
                                "name": tool.name,
                                "description": tool.description or "",
                                "input_schema": tool.inputSchema,
                            }
                            for tool in page.tools
                        )
                        cursor = page.nextCursor
                        if not cursor:
                            return tools
        except MCPError as exc:
            if require_connected:
                await self._set_status(server_id, "connected", "Error", str(exc))
            raise
        except TimeoutError as exc:
            if require_connected:
                await self._set_status(
                    server_id, "connected", "Error", "MCP tool discovery timed out"
                )
            raise MCPError("MCP_TIMEOUT", "MCP connection timed out") from exc
        except Exception as exc:
            if require_connected:
                await self._set_status(
                    server_id,
                    "connected",
                    "Error",
                    f"{type(exc).__name__}: tool discovery failed",
                )
                raise MCPError(
                    "MCP_TOOL_DISCOVERY_FAILED", "MCP tool discovery failed"
                ) from exc
            raise MCPError("MCP_CONNECTION_FAILED", "MCP connection failed") from exc

    async def _required_server(self, server_id: str) -> dict[str, Any]:
        server = await self.get(server_id)
        if server is None:
            raise MCPError("MCP_NOT_FOUND", f"MCP server {server_id} was not found")
        if not server["transport"]:
            raise MCPError("MCP_CONFIGURATION_ERROR", "MCP server is not configured")
        return server

    async def _connected_server(self, server_id: str) -> dict[str, Any]:
        server = await self._required_server(server_id)
        if server["desired_state"] != "connected":
            raise MCPError("MCP_NOT_CONNECTED", f"MCP server {server_id} is disconnected")
        return server

    async def _set_status(
        self,
        server_id: str,
        desired_state: str,
        health_status: str,
        last_error: str | None,
    ) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            _get_required(connection, server_id)
            connection.execute(
                """
                UPDATE mcp_servers
                SET desired_state = ?, health_status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (desired_state, health_status, last_error, _utc_now(), server_id),
            )
            return _get_required(connection, server_id)

        return await self.database.run(operation)


def _validate_configuration(
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    transport = payload.get("transport")
    configuration = payload.get("configuration")
    if transport not in {"stdio", "streamable_http"}:
        raise MCPError(
            "VALIDATION_ERROR", "transport must be stdio or streamable_http"
        )
    if not isinstance(configuration, dict):
        raise MCPError("VALIDATION_ERROR", "configuration must be an object")
    public: dict[str, Any] = {}
    references: dict[str, Any] = {}
    if transport == "stdio":
        command = configuration.get("command")
        args = configuration.get("args", [])
        if not isinstance(command, str) or not command:
            raise MCPError("VALIDATION_ERROR", "stdio command is required")
        if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
            raise MCPError("VALIDATION_ERROR", "stdio args must be a string array")
        public.update({"command": command, "args": args})
        cwd = configuration.get("cwd")
        if cwd is not None:
            if not isinstance(cwd, str):
                raise MCPError("VALIDATION_ERROR", "stdio cwd must be a string")
            public["cwd"] = cwd
        references["env"] = _parse_references(configuration.get("env", {}), "env")
    else:
        url = configuration.get("url")
        parsed = urlparse(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise MCPError("VALIDATION_ERROR", "streamable_http url must be http(s)")
        public["url"] = url
        references["headers"] = _parse_references(
            configuration.get("headers", {}), "headers"
        )
    return transport, public, references


def _parse_references(values: Any, field: str) -> dict[str, str]:
    if not isinstance(values, dict):
        raise MCPError("VALIDATION_ERROR", f"{field} must be an object")
    references: dict[str, str] = {}
    for name, value in values.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise MCPError("VALIDATION_ERROR", f"{field} values must be strings")
        match = ENV_REFERENCE.fullmatch(value)
        if not match:
            raise MCPError(
                "VALIDATION_ERROR", f"{field}.{name} must use $env:VARIABLE"
            )
        references[name] = match.group(1)
    return references


def _connection_config(server: dict[str, Any]) -> dict[str, Any]:
    configuration = server["configuration"]
    result = {"transport": server["transport"]}
    if server["transport"] == "stdio":
        result.update(
            {
                "command": configuration["command"],
                "args": configuration.get("args", []),
            }
        )
        if configuration.get("cwd"):
            result["cwd"] = str(Path(configuration["cwd"]).resolve())
        if configuration.get("env"):
            result["env"] = _resolve_references(configuration["env"])
    else:
        result.update(
            {
                "url": configuration["url"],
                "timeout": 15.0,
                "sse_read_timeout": 15.0,
            }
        )
        if configuration.get("headers"):
            result["headers"] = _resolve_references(configuration["headers"])
    return result


def _resolve_references(references: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name, value in references.items():
        match = ENV_REFERENCE.fullmatch(value)
        if not match or match.group(1) not in os.environ:
            variable = match.group(1) if match else value
            raise MCPError(
                "MCP_CONFIGURATION_ERROR", f"Environment variable {variable} is not set"
            )
        resolved[name] = os.environ[match.group(1)]
    return resolved


def _get_required(connection: sqlite3.Connection, server_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM mcp_servers WHERE id = ?", (server_id,)
    ).fetchone()
    if row is None:
        raise MCPError("MCP_NOT_FOUND", f"MCP server {server_id} was not found")
    return _decode_server(row)


def _decode_server(row: sqlite3.Row) -> dict[str, Any]:
    server = dict(row)
    public = json.loads(server.pop("public_config"))
    references = json.loads(server.pop("environment_refs"))
    for group, values in references.items():
        if values:
            public[group] = {name: f"$env:{variable}" for name, variable in values.items()}
    server["configuration"] = public
    return server


def _serialize_content(content: Any) -> Any:
    if hasattr(content, "model_dump"):
        return content.model_dump(mode="json", by_alias=True)
    return str(content)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
