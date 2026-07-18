from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from big_bear_ai.database import Database


class UnknownResourceError(ValueError):
    pass


class ReadOnlyResourceError(PermissionError):
    pass


class ResourceValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    table: str
    fields: frozenset[str]
    required: frozenset[str]
    search_fields: tuple[str, ...]
    json_fields: frozenset[str] = field(default_factory=frozenset)
    boolean_fields: frozenset[str] = field(default_factory=frozenset)
    defaults: dict[str, Any] = field(default_factory=dict)
    read_only_field: str | None = None


SPECS: dict[str, ResourceSpec] = {
    "project": ResourceSpec(
        table="projects",
        fields=frozenset({"name", "description", "status"}),
        required=frozenset({"name"}),
        search_fields=("name", "description"),
        defaults={"description": "", "status": "draft"},
    ),
    "design": ResourceSpec(
        table="test_designs",
        fields=frozenset(
            {
                "project_id",
                "title",
                "content",
                "status",
                "source_thread_id",
                "source_run_id",
            }
        ),
        required=frozenset({"project_id", "title"}),
        search_fields=("title", "content"),
        defaults={"content": "", "status": "draft"},
    ),
    "rule": ResourceSpec(
        table="rules",
        fields=frozenset(
            {"title", "description", "definition", "tags", "author", "enabled"}
        ),
        required=frozenset({"title", "definition"}),
        search_fields=("title", "description", "definition", "tags"),
        json_fields=frozenset({"tags"}),
        boolean_fields=frozenset({"enabled", "official", "read_only"}),
        defaults={
            "description": "",
            "tags": [],
            "author": "用户",
            "enabled": True,
        },
        read_only_field="read_only",
    ),
    "prompt": ResourceSpec(
        table="prompts",
        fields=frozenset(
            {"title", "description", "template", "variables", "tags", "author"}
        ),
        required=frozenset({"title", "template"}),
        search_fields=("title", "description", "template", "tags"),
        json_fields=frozenset({"variables", "tags"}),
        boolean_fields=frozenset({"read_only"}),
        defaults={"description": "", "variables": [], "tags": [], "author": "用户"},
        read_only_field="read_only",
    ),
    "agent": ResourceSpec(
        table="agent_profiles",
        fields=frozenset(
            {
                "name",
                "description",
                "instructions",
                "category",
                "model_override",
                "allowed_rule_ids",
                "allowed_plugin_ids",
                "allowed_document_ids",
                "author",
            }
        ),
        required=frozenset({"name", "instructions"}),
        search_fields=("name", "description", "instructions", "category"),
        json_fields=frozenset(
            {"allowed_rule_ids", "allowed_plugin_ids", "allowed_document_ids"}
        ),
        boolean_fields=frozenset({"read_only"}),
        defaults={
            "description": "",
            "category": "自定义",
            "allowed_rule_ids": [],
            "allowed_plugin_ids": [],
            "allowed_document_ids": [],
            "author": "用户",
        },
        read_only_field="read_only",
    ),
}


class ResourceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _spec(self, resource: str) -> ResourceSpec:
        try:
            return SPECS[resource]
        except KeyError as exc:
            raise UnknownResourceError(f"Unknown resource: {resource}") from exc

    async def create(self, resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        spec = self._spec(resource)
        unknown = set(payload) - spec.fields
        if unknown:
            raise ResourceValidationError(f"Unknown fields: {', '.join(sorted(unknown))}")
        values = {**spec.defaults, **payload}
        missing = [name for name in spec.required if not values.get(name)]
        if missing:
            raise ResourceValidationError(f"Missing fields: {', '.join(sorted(missing))}")

        identifier = str(uuid4())
        timestamp = _utc_now()
        columns = ["id", *values.keys(), "created_at", "updated_at"]
        encoded = [identifier, *(_encode(spec, key, value) for key, value in values.items()), timestamp, timestamp]
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {spec.table} ({', '.join(columns)}) VALUES ({placeholders})"

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            connection.execute(sql, encoded)
            return _get_required(connection, spec, identifier)

        return await self.database.run(operation)

    async def get(self, resource: str, resource_id: str) -> dict[str, Any] | None:
        spec = self._spec(resource)

        def operation(connection: sqlite3.Connection) -> dict[str, Any] | None:
            row = connection.execute(
                f"SELECT * FROM {spec.table} WHERE id = ?", (resource_id,)
            ).fetchone()
            return _decode_row(spec, row) if row else None

        return await self.database.run(operation)

    async def list(
        self,
        resource: str,
        *,
        search: str = "",
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        spec = self._spec(resource)
        if not 1 <= limit <= 100:
            raise ResourceValidationError("limit must be between 1 and 100")
        try:
            offset = int(cursor or "0")
        except ValueError as exc:
            raise ResourceValidationError("cursor must be an integer offset") from exc
        if offset < 0:
            raise ResourceValidationError("cursor must not be negative")

        parameters: list[Any] = []
        where = ""
        if search:
            pattern = f"%{search.lower()}%"
            where = " WHERE " + " OR ".join(
                f"LOWER(COALESCE({field}, '')) LIKE ?" for field in spec.search_fields
            )
            parameters.extend(pattern for _ in spec.search_fields)
        order = (
            f"{spec.read_only_field} DESC, updated_at DESC, id"
            if spec.read_only_field
            else "updated_at DESC, id"
        )

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            total = connection.execute(
                f"SELECT COUNT(*) FROM {spec.table}{where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM {spec.table}{where} ORDER BY {order} LIMIT ? OFFSET ?",
                [*parameters, limit, offset],
            ).fetchall()
            next_offset = offset + len(rows)
            return {
                "items": [_decode_row(spec, row) for row in rows],
                "total": total,
                "next_cursor": str(next_offset) if next_offset < total else None,
            }

        return await self.database.run(operation)

    async def update(
        self, resource: str, resource_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        spec = self._spec(resource)
        unknown = set(payload) - spec.fields
        if unknown:
            raise ResourceValidationError(f"Unknown fields: {', '.join(sorted(unknown))}")

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            current = _get_required(connection, spec, resource_id)
            if spec.read_only_field and current.get(spec.read_only_field):
                raise ReadOnlyResourceError(f"{resource} {resource_id} is read-only")
            if not payload:
                return current
            assignments = [f"{key} = ?" for key in payload]
            assignments.append("updated_at = ?")
            values = [_encode(spec, key, value) for key, value in payload.items()]
            values.extend([_utc_now(), resource_id])
            connection.execute(
                f"UPDATE {spec.table} SET {', '.join(assignments)} WHERE id = ?", values
            )
            return _get_required(connection, spec, resource_id)

        return await self.database.run(operation)

    async def delete(self, resource: str, resource_id: str) -> None:
        spec = self._spec(resource)

        def operation(connection: sqlite3.Connection) -> None:
            current = _get_required(connection, spec, resource_id)
            if spec.read_only_field and current.get(spec.read_only_field):
                raise ReadOnlyResourceError(f"{resource} {resource_id} is read-only")
            connection.execute(f"DELETE FROM {spec.table} WHERE id = ?", (resource_id,))

        await self.database.run(operation)


def _get_required(
    connection: sqlite3.Connection, spec: ResourceSpec, resource_id: str
) -> dict[str, Any]:
    row = connection.execute(
        f"SELECT * FROM {spec.table} WHERE id = ?", (resource_id,)
    ).fetchone()
    if row is None:
        raise KeyError(resource_id)
    return _decode_row(spec, row)


def _encode(spec: ResourceSpec, key: str, value: Any) -> Any:
    if key in spec.json_fields:
        return json.dumps(value, ensure_ascii=False)
    if key in spec.boolean_fields:
        return int(bool(value))
    return value


def _decode_row(spec: ResourceSpec, row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in spec.json_fields:
        if key in result:
            result[key] = json.loads(result[key])
    for key in spec.boolean_fields:
        if key in result:
            result[key] = bool(result[key])
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

