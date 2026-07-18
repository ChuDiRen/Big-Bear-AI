from __future__ import annotations

import asyncio
import sqlite3
from typing import Any, TypedDict

from big_bear_ai.database import Database
from big_bear_ai.config import Settings
from big_bear_ai.repositories.resources import (
    ReadOnlyResourceError,
    ResourceRepository,
    ResourceValidationError,
    UnknownResourceError,
)
from big_bear_ai.services.documents import DocumentError, DocumentService
from big_bear_ai.services.plugins import PluginError, PluginService
from big_bear_ai.services.mcp import MCPError, MCPService


class ErrorPayload(TypedDict, total=False):
    code: str
    message: str
    fields: dict[str, str]


class ManagementResult(TypedDict):
    ok: bool
    data: Any
    error: ErrorPayload | None


SUPPORTED_OPERATIONS = frozenset(
    {"list", "get", "create", "update", "delete", "action"}
)


class ManagementService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.repository = ResourceRepository(database)
        self.documents = DocumentService(database, settings)
        self.plugins = PluginService(database)
        self.mcp = MCPService(database, settings)
        self._initialized = False
        self._initialize_lock = asyncio.Lock()

    async def handle(self, request: dict[str, Any]) -> ManagementResult:
        await self._ensure_initialized()
        try:
            operation = request.get("operation")
            resource = request.get("resource")
            if operation not in SUPPORTED_OPERATIONS:
                raise ResourceValidationError(
                    "operation must be one of: create, delete, get, list, update"
                )
            if not isinstance(resource, str) or not resource:
                raise ResourceValidationError("resource is required")

            if resource == "document":
                return await self._handle_documents(operation, request)
            if resource == "plugin":
                return await self._handle_plugins(operation, request)
            if resource == "mcp":
                return await self._handle_mcp(operation, request)

            if operation == "list":
                query = request.get("query") or {}
                if not isinstance(query, dict):
                    raise ResourceValidationError("query must be an object")
                data = await self.repository.list(
                    resource,
                    search=str(query.get("search", "")),
                    limit=int(query.get("limit", 50)),
                    cursor=query.get("cursor"),
                )
                return _success(data)

            resource_id = request.get("resource_id")
            if operation in {"get", "update", "delete"} and not resource_id:
                raise ResourceValidationError("resource_id is required")

            if operation == "get":
                data = await self.repository.get(resource, str(resource_id))
                if data is None:
                    return _failure("NOT_FOUND", f"{resource} {resource_id} was not found")
                return _success(data)

            payload = request.get("payload") or {}
            if not isinstance(payload, dict):
                raise ResourceValidationError("payload must be an object")
            if operation == "create":
                return _success(await self.repository.create(resource, payload))
            if operation == "update":
                return _success(
                    await self.repository.update(resource, str(resource_id), payload)
                )

            await self.repository.delete(resource, str(resource_id))
            return _success({"id": str(resource_id), "deleted": True})
        except UnknownResourceError as exc:
            return _failure("VALIDATION_ERROR", f"resource is invalid: {exc}")
        except ResourceValidationError as exc:
            return _failure("VALIDATION_ERROR", str(exc))
        except ReadOnlyResourceError as exc:
            return _failure("READ_ONLY_RESOURCE", str(exc))
        except DocumentError as exc:
            return _failure(exc.code, str(exc))
        except PluginError as exc:
            return _failure(exc.code, str(exc))
        except MCPError as exc:
            return _failure(exc.code, str(exc))
        except KeyError:
            return _failure(
                "NOT_FOUND",
                f"{request.get('resource')} {request.get('resource_id')} was not found",
            )
        except (sqlite3.IntegrityError, ValueError) as exc:
            return _failure("VALIDATION_ERROR", str(exc))

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if not self._initialized:
                await self.database.initialize()
                self._initialized = True

    async def _handle_documents(
        self, operation: str, request: dict[str, Any]
    ) -> ManagementResult:
        if operation == "list":
            query = request.get("query") or {}
            if not isinstance(query, dict):
                raise ResourceValidationError("query must be an object")
            return _success(
                await self.documents.list(
                    search=str(query.get("search", "")),
                    limit=int(query.get("limit", 50)),
                    cursor=query.get("cursor"),
                )
            )
        resource_id = request.get("resource_id")
        if operation == "get":
            if not resource_id:
                raise ResourceValidationError("resource_id is required")
            document = await self.documents.get(str(resource_id))
            if document is None:
                return _failure("NOT_FOUND", f"document {resource_id} was not found")
            return _success(document)
        if operation == "delete":
            if not resource_id:
                raise ResourceValidationError("resource_id is required")
            await self.documents.delete(str(resource_id))
            return _success({"id": str(resource_id), "deleted": True})
        if operation == "action":
            payload = request.get("payload") or {}
            if not isinstance(payload, dict):
                raise ResourceValidationError("payload must be an object")
            action = payload.get("action")
            if action == "upload":
                return _success(
                    await self.documents.upload(
                        {key: value for key, value in payload.items() if key != "action"}
                    )
                )
            if action == "search":
                return _success(
                    await self.documents.search(
                        str(payload.get("query", "")),
                        limit=int(payload.get("limit", 8)),
                        document_ids=payload.get("document_ids"),
                    )
                )
            raise ResourceValidationError("document action must be upload or search")
        raise ResourceValidationError(
            "document operation must be action, delete, get, or list"
        )

    async def _handle_plugins(
        self, operation: str, request: dict[str, Any]
    ) -> ManagementResult:
        if operation == "list":
            return _success(await self.plugins.list())
        if operation == "get":
            plugin_id = request.get("resource_id")
            if not plugin_id:
                raise ResourceValidationError("resource_id is required")
            plugin = await self.plugins.get(str(plugin_id))
            if plugin is None:
                return _failure("NOT_FOUND", f"plugin {plugin_id} was not found")
            return _success(plugin)
        if operation != "action":
            raise ResourceValidationError("plugin operation must be action, get, or list")
        payload = request.get("payload") or {}
        if not isinstance(payload, dict):
            raise ResourceValidationError("payload must be an object")
        action = payload.get("action")
        plugin_id = payload.get("plugin_id")
        if not isinstance(plugin_id, str) or not plugin_id:
            raise ResourceValidationError("plugin_id is required")
        if action == "install":
            return _success(
                await self.plugins.install(plugin_id, payload.get("configuration"))
            )
        if action == "configure":
            configuration = payload.get("configuration")
            if not isinstance(configuration, dict):
                raise ResourceValidationError("configuration must be an object")
            return _success(await self.plugins.configure(plugin_id, configuration))
        if action in {"enable", "disable"}:
            return _success(
                await self.plugins.set_enabled(plugin_id, action == "enable")
            )
        if action == "uninstall":
            return _success(await self.plugins.uninstall(plugin_id))
        if action == "call":
            return _success(await self.plugins.call(plugin_id, payload.get("input") or {}))
        raise ResourceValidationError(
            "plugin action must be call, configure, disable, enable, install, or uninstall"
        )

    async def _handle_mcp(
        self, operation: str, request: dict[str, Any]
    ) -> ManagementResult:
        if operation == "list":
            query = request.get("query") or {}
            return _success(await self.mcp.list(search=str(query.get("search", ""))))
        server_id = request.get("resource_id")
        if operation == "get":
            if not server_id:
                raise ResourceValidationError("resource_id is required")
            server = await self.mcp.get(str(server_id))
            if server is None:
                return _failure("NOT_FOUND", f"mcp {server_id} was not found")
            return _success(server)
        payload = request.get("payload") or {}
        if not isinstance(payload, dict):
            raise ResourceValidationError("payload must be an object")
        if operation == "create":
            return _success(await self.mcp.create(payload))
        if operation == "update":
            if not server_id:
                raise ResourceValidationError("resource_id is required")
            return _success(await self.mcp.configure(str(server_id), payload))
        if operation == "delete":
            if not server_id:
                raise ResourceValidationError("resource_id is required")
            await self.mcp.delete(str(server_id))
            return _success({"id": str(server_id), "deleted": True})
        if operation != "action":
            raise ResourceValidationError(
                "mcp operation must be action, create, delete, get, list, or update"
            )
        if not server_id:
            raise ResourceValidationError("resource_id is required")
        action = payload.get("action")
        if action == "connect":
            return _success(await self.mcp.connect(str(server_id)))
        if action == "disconnect":
            return _success(await self.mcp.disconnect(str(server_id)))
        if action == "list_tools":
            return _success(await self.mcp.list_tools(str(server_id)))
        if action == "call":
            return _success(
                await self.mcp.call_tool(
                    str(server_id),
                    str(payload.get("tool_name") or ""),
                    payload.get("arguments") or {},
                )
            )
        raise ResourceValidationError(
            "mcp action must be call, connect, disconnect, or list_tools"
        )


def _success(data: Any) -> ManagementResult:
    return {"ok": True, "data": data, "error": None}


def _failure(code: str, message: str) -> ManagementResult:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}}
