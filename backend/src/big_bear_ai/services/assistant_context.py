from __future__ import annotations

from typing import Any

from big_bear_ai.database import Database
from big_bear_ai.repositories.resources import ResourceRepository
from big_bear_ai.services.documents import DocumentService
from big_bear_ai.services.mcp import MCPService
from big_bear_ai.services.plugins import PluginService


MODES = frozenset({"auto", "design", "analysis", "execution"})


class AssistantContextService:
    def __init__(
        self,
        database: Database,
        documents: DocumentService,
        plugins: PluginService,
        mcp: MCPService,
    ) -> None:
        self.database = database
        self.repository = ResourceRepository(database)
        self.documents = documents
        self.plugins = plugins
        self.mcp = mcp

    async def resolve(self, context: dict[str, Any] | None) -> dict[str, Any]:
        await self.database.initialize()
        requested = context or {}
        mode = str(requested.get("mode") or "auto")
        if mode not in MODES:
            mode = "auto"

        project = await self._optional_resource("project", requested.get("project_id"))
        agent = await self._optional_resource("agent", requested.get("agent_id"))
        prompt = await self._optional_resource("prompt", requested.get("prompt_id"))
        rule = await self._optional_resource("rule", requested.get("rule_id"))
        supplied_prompt_variables = requested.get("prompt_variables")
        prompt_variables = (
            {
                str(key): str(value)
                for key, value in supplied_prompt_variables.items()
                if isinstance(key, str)
            }
            if isinstance(supplied_prompt_variables, dict)
            else {}
        )

        rules = (await self.repository.list("rule", limit=100))["items"]
        enabled_rules = [rule for rule in rules if rule["enabled"]]
        if rule is not None:
            enabled_rules = [rule] if rule["enabled"] else []
        plugin_items = (await self.plugins.list())["items"]
        installed_plugins = [
            plugin for plugin in plugin_items if plugin["installed"] and plugin["enabled"]
        ]
        documents = (await self.documents.list(limit=100))["items"]
        mcp_servers = (await self.mcp.list())["items"]
        connected_mcp = [
            server
            for server in mcp_servers
            if server["desired_state"] == "connected"
            and server["health_status"] == "Connected"
        ]

        restricted = agent is not None
        if restricted:
            rule_ids = set(agent["allowed_rule_ids"])
            plugin_ids = set(agent["allowed_plugin_ids"])
            document_ids = set(agent["allowed_document_ids"])
            enabled_rules = [rule for rule in enabled_rules if rule["id"] in rule_ids]
            installed_plugins = [
                plugin for plugin in installed_plugins if plugin["id"] in plugin_ids
            ]
            documents = [document for document in documents if document["id"] in document_ids]

        resolved = {
            "mode": mode,
            "project": project,
            "agent": agent,
            "prompt": prompt,
            "prompt_variables": prompt_variables,
            "rule": rule,
            "rules": enabled_rules,
            "plugins": installed_plugins,
            "documents": documents,
            "mcp_servers": connected_mcp,
            "restricted": restricted,
            "allowed_plugin_ids": [plugin["id"] for plugin in installed_plugins],
            "allowed_document_ids": [document["id"] for document in documents],
        }
        resolved["directive"] = _format_directive(resolved)
        return resolved

    async def _optional_resource(
        self, resource: str, resource_id: Any
    ) -> dict[str, Any] | None:
        if not isinstance(resource_id, str) or not resource_id:
            return None
        return await self.repository.get(resource, resource_id)


def _format_directive(context: dict[str, Any]) -> str:
    lines = ["## Big Bear AI runtime context", f"Mode: {context['mode']}"]
    if context["project"]:
        lines.append(f"Project: {context['project']['name']}")
        if context["project"]["description"]:
            lines.append(f"Project description: {context['project']['description']}")
    if context["agent"]:
        lines.append(f"Agent: {context['agent']['name']}")
        lines.append(f"Agent instructions: {context['agent']['instructions']}")
    if context["prompt"]:
        lines.append(f"Selected prompt: {context['prompt']['title']}")
        template = context["prompt"]["template"]
        for variable in context["prompt"]["variables"]:
            placeholder = "{" + str(variable) + "}"
            template = template.replace(
                placeholder, context["prompt_variables"].get(str(variable), "")
            )
        lines.append(template)
    if context["rules"]:
        lines.append("Enabled rules:")
        lines.extend(
            f"- {rule['title']}: {rule['definition']}" for rule in context["rules"]
        )
    if context["plugins"]:
        lines.append(
            "Installed plugins: "
            + ", ".join(plugin["name"] for plugin in context["plugins"])
        )
    if context["documents"]:
        lines.append(
            "Available knowledge: "
            + ", ".join(document["title"] for document in context["documents"])
        )
    if context["mcp_servers"]:
        lines.append(
            "Connected MCP servers: "
            + ", ".join(server["name"] for server in context["mcp_servers"])
        )
    return "\n".join(lines)
