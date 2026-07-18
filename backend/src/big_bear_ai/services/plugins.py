from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from big_bear_ai.database import Database


class PluginError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


PluginFunction = Callable[[dict[str, Any], dict[str, Any]], Any]


class PluginService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def list(self) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            rows = connection.execute(
                """
                SELECT c.*, i.enabled, i.configuration, i.installed_at
                FROM plugin_catalogue AS c
                LEFT JOIN plugin_installations AS i ON i.plugin_id = c.id
                ORDER BY c.name
                """
            ).fetchall()
            return {"items": [_decode_plugin(row) for row in rows], "total": len(rows)}

        return await self.database.run(operation)

    async def get(self, plugin_id: str) -> dict[str, Any] | None:
        return await self.database.run(
            lambda connection: _get_plugin(connection, plugin_id, required=False)
        )

    async def install(
        self, plugin_id: str, configuration: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        config = configuration or {}
        _validate_configuration(plugin_id, config)
        timestamp = _utc_now()

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            _get_plugin(connection, plugin_id)
            connection.execute(
                """
                INSERT INTO plugin_installations(
                    plugin_id, enabled, configuration, installed_at, updated_at
                ) VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    enabled = 1,
                    configuration = excluded.configuration,
                    updated_at = excluded.updated_at
                """,
                (plugin_id, json.dumps(config, ensure_ascii=False), timestamp, timestamp),
            )
            return _get_plugin(connection, plugin_id)

        return await self.database.run(operation)

    async def configure(
        self, plugin_id: str, configuration: dict[str, Any]
    ) -> dict[str, Any]:
        _validate_configuration(plugin_id, configuration)

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            plugin = _get_plugin(connection, plugin_id)
            if not plugin["installed"]:
                raise PluginError("PLUGIN_NOT_INSTALLED", f"Plugin {plugin_id} is not installed")
            connection.execute(
                "UPDATE plugin_installations SET configuration = ?, updated_at = ? WHERE plugin_id = ?",
                (json.dumps(configuration, ensure_ascii=False), _utc_now(), plugin_id),
            )
            return _get_plugin(connection, plugin_id)

        return await self.database.run(operation)

    async def set_enabled(self, plugin_id: str, enabled: bool) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            plugin = _get_plugin(connection, plugin_id)
            if not plugin["installed"]:
                raise PluginError("PLUGIN_NOT_INSTALLED", f"Plugin {plugin_id} is not installed")
            connection.execute(
                "UPDATE plugin_installations SET enabled = ?, updated_at = ? WHERE plugin_id = ?",
                (int(enabled), _utc_now(), plugin_id),
            )
            return _get_plugin(connection, plugin_id)

        return await self.database.run(operation)

    async def uninstall(self, plugin_id: str) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            _get_plugin(connection, plugin_id)
            connection.execute(
                "DELETE FROM plugin_installations WHERE plugin_id = ?", (plugin_id,)
            )
            return _get_plugin(connection, plugin_id)

        return await self.database.run(operation)

    async def call(self, plugin_id: str, tool_input: dict[str, Any]) -> Any:
        plugin = await self.get(plugin_id)
        if plugin is None:
            raise PluginError("PLUGIN_NOT_FOUND", f"Unknown plugin: {plugin_id}")
        if not plugin["installed"]:
            raise PluginError("PLUGIN_NOT_INSTALLED", f"Plugin {plugin_id} is not installed")
        if not plugin["enabled"]:
            raise PluginError("PLUGIN_DISABLED", f"Plugin {plugin_id} is disabled")
        if not isinstance(tool_input, dict):
            raise PluginError("VALIDATION_ERROR", "plugin input must be an object")
        function = PLUGIN_FUNCTIONS[plugin_id]
        return await asyncio.to_thread(function, tool_input, plugin["configuration"])


def _get_plugin(
    connection: sqlite3.Connection, plugin_id: str, *, required: bool = True
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT c.*, i.enabled, i.configuration, i.installed_at
        FROM plugin_catalogue AS c
        LEFT JOIN plugin_installations AS i ON i.plugin_id = c.id
        WHERE c.id = ?
        """,
        (plugin_id,),
    ).fetchone()
    if row is None:
        if required:
            raise PluginError("PLUGIN_NOT_FOUND", f"Unknown plugin: {plugin_id}")
        return None
    return _decode_plugin(row)


def _decode_plugin(row: sqlite3.Row) -> dict[str, Any]:
    plugin = dict(row)
    plugin["installed"] = plugin["installed_at"] is not None
    plugin["enabled"] = bool(plugin["enabled"]) if plugin["installed"] else False
    plugin["configuration"] = (
        json.loads(plugin["configuration"]) if plugin["configuration"] else {}
    )
    plugin["config_schema"] = json.loads(plugin["config_schema"])
    return plugin


def _validate_configuration(plugin_id: str, configuration: dict[str, Any]) -> None:
    if plugin_id not in PLUGIN_FUNCTIONS:
        raise PluginError("PLUGIN_NOT_FOUND", f"Unknown plugin: {plugin_id}")
    if not isinstance(configuration, dict):
        raise PluginError("VALIDATION_ERROR", "plugin configuration must be an object")


def _data_generator(tool_input: dict[str, Any], _configuration: dict[str, Any]) -> list[dict[str, Any]]:
    count = tool_input.get("count", 1)
    schema = tool_input.get("schema")
    if not isinstance(count, int) or not 1 <= count <= 100:
        raise PluginError("VALIDATION_ERROR", "count must be between 1 and 100")
    if not isinstance(schema, dict) or not schema:
        raise PluginError("VALIDATION_ERROR", "schema must be a non-empty object")
    supported = {"string", "integer", "number", "boolean"}
    if any(value not in supported for value in schema.values()):
        raise PluginError("VALIDATION_ERROR", "schema contains an unsupported type")

    def value(kind: str, index: int) -> Any:
        return {
            "string": f"sample-{index}",
            "integer": index,
            "number": float(index),
            "boolean": index % 2 == 1,
        }[kind]

    return [
        {name: value(kind, index) for name, kind in schema.items()}
        for index in range(1, count + 1)
    ]


def _api_validator(tool_input: dict[str, Any], _configuration: dict[str, Any]) -> dict[str, Any]:
    schema = tool_input.get("schema")
    if not isinstance(schema, dict):
        raise PluginError("VALIDATION_ERROR", "schema must be an object")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise PluginError("VALIDATION_ERROR", f"invalid JSON Schema: {exc.message}") from exc
    errors = sorted(
        Draft202012Validator(schema).iter_errors(tool_input.get("instance")),
        key=lambda error: list(error.absolute_path),
    )
    return {
        "valid": not errors,
        "errors": [
            {"path": list(error.absolute_path), "message": error.message}
            for error in errors
        ],
    }


def _log_analyzer(tool_input: dict[str, Any], _configuration: dict[str, Any]) -> dict[str, Any]:
    text = tool_input.get("text")
    if not isinstance(text, str) or len(text) > 100_000:
        raise PluginError("VALIDATION_ERROR", "text must be at most 100000 characters")
    requested_level = str(tool_input.get("level", "")).upper()
    contains = str(tool_input.get("contains", "")).lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if requested_level:
        lines = [line for line in lines if line.upper().startswith(requested_level)]
    if contains:
        lines = [line for line in lines if contains in line.lower()]
    levels = Counter()
    for line in lines:
        match = re.match(r"^(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)\b", line.upper())
        levels[match.group(1) if match else "OTHER"] += 1
    return {"count": len(lines), "levels": dict(levels), "lines": lines[:200]}


PLUGIN_FUNCTIONS: dict[str, PluginFunction] = {
    "data-generator": _data_generator,
    "api-validator": _api_validator,
    "log-analyzer": _log_analyzer,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
