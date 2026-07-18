from __future__ import annotations

import json
from typing import Any

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool, ToolException

from big_bear_ai.repositories.resources import ResourceRepository
from big_bear_ai.services.documents import DocumentService
from big_bear_ai.services.mcp import MCPService
from big_bear_ai.services.plugins import PluginService


def create_application_tools(
    repository: ResourceRepository,
    documents: DocumentService,
    plugins: PluginService,
    mcp: MCPService,
) -> list[BaseTool]:
    @tool
    async def search_knowledge(query: str, runtime: ToolRuntime) -> str:
        """Search the knowledge base for excerpts relevant to a query."""
        resolved = _resolved(runtime)
        document_ids = (
            resolved.get("allowed_document_ids") if resolved.get("restricted") else None
        )
        results = await documents.search(query, document_ids=document_ids)
        return json.dumps(results, ensure_ascii=False)

    @tool
    async def call_plugin(
        plugin_id: str, tool_input: dict[str, Any], runtime: ToolRuntime
    ) -> str:
        """Call an installed Big Bear plugin by ID with structured input."""
        resolved = _resolved(runtime)
        if resolved.get("restricted") and plugin_id not in resolved.get(
            "allowed_plugin_ids", []
        ):
            raise ToolException(f"Plugin {plugin_id} is not allowed for this Agent")
        result = await plugins.call(plugin_id, tool_input)
        return json.dumps(result, ensure_ascii=False)

    @tool
    async def list_mcp_tools(server_id: str, runtime: ToolRuntime) -> str:
        """List tools exposed by a connected MCP server."""
        _require_connected_mcp(server_id, runtime)
        return json.dumps(await mcp.list_tools(server_id), ensure_ascii=False)

    @tool
    async def call_mcp_tool(
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        runtime: ToolRuntime,
    ) -> str:
        """Call a tool on a connected MCP server."""
        _require_connected_mcp(server_id, runtime)
        result = await mcp.call_tool(server_id, tool_name, arguments)
        return json.dumps(result, ensure_ascii=False)

    @tool
    async def save_test_design(
        title: str,
        content: str,
        runtime: ToolRuntime,
        project_id: str | None = None,
    ) -> str:
        """Save a generated test design to the selected project."""
        resolved = _resolved(runtime)
        selected = resolved.get("project")
        target_id = project_id or (selected["id"] if selected else None)
        if target_id is None:
            raise ToolException("Select or create a project before saving a test design")
        if selected and target_id != selected["id"]:
            raise ToolException("The target project does not match the selected project")
        design = await repository.create(
            "design",
            {"project_id": target_id, "title": title, "content": content},
        )
        return json.dumps(design, ensure_ascii=False)

    return [
        search_knowledge,
        call_plugin,
        list_mcp_tools,
        call_mcp_tool,
        save_test_design,
    ]


def _resolved(runtime: ToolRuntime) -> dict[str, Any]:
    return runtime.state.get("resolved_context") or {}


def _require_connected_mcp(server_id: str, runtime: ToolRuntime) -> None:
    connected_ids = {
        server["id"] for server in _resolved(runtime).get("mcp_servers", [])
    }
    if server_id not in connected_ids:
        raise ToolException(f"MCP server {server_id} is not connected")

