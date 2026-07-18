from __future__ import annotations

import asyncio
from typing import Any
from typing_extensions import NotRequired

from deepagents import create_deep_agent
from deepagents.graph import DeepAgentState
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from big_bear_ai.config import Settings, load_settings
from big_bear_ai.database import Database
from big_bear_ai.models import create_chat_model
from big_bear_ai.repositories.resources import ResourceRepository
from big_bear_ai.services.assistant_context import AssistantContextService
from big_bear_ai.services.documents import DocumentService
from big_bear_ai.services.mcp import MCPService
from big_bear_ai.services.plugins import PluginService
from big_bear_ai.tools.application import create_application_tools


class AssistantState(DeepAgentState):
    context: NotRequired[dict[str, Any]]
    resolved_context: NotRequired[dict[str, Any]]


def build_assistant_graph(
    settings: Settings | None = None,
    *,
    model: BaseChatModel | None = None,
):
    active_settings = settings or load_settings()
    database = Database(active_settings.database_path)
    repository = ResourceRepository(database)
    documents = DocumentService(database, active_settings)
    plugins = PluginService(database)
    mcp = MCPService(database, active_settings)
    context_service = AssistantContextService(
        database, documents=documents, plugins=plugins, mcp=mcp
    )
    application_tools = create_application_tools(
        repository, documents=documents, plugins=plugins, mcp=mcp
    )

    default_model = model or create_chat_model(active_settings)
    model_cache: dict[str, BaseChatModel] = {active_settings.model: default_model}

    @wrap_model_call(state_schema=AssistantState)
    async def inject_runtime_context(
        request: ModelRequest,
        handler,
    ) -> ModelResponse:
        existing = request.system_message
        blocks = list(existing.content_blocks) if existing else []
        directive = (request.state.get("resolved_context") or {}).get(
            "directive", "## Big Bear AI runtime context\nMode: auto"
        )
        blocks.append({"type": "text", "text": directive})
        agent = (request.state.get("resolved_context") or {}).get("agent") or {}
        model_name = str(agent.get("model_override") or "").strip()
        selected_model = default_model
        if model_name:
            selected_model = model_cache.get(model_name)
            if selected_model is None:
                selected_model = create_chat_model(active_settings, model_name)
                model_cache[model_name] = selected_model
        return await handler(
            request.override(
                model=selected_model,
                system_message=SystemMessage(content=blocks),
            )
        )

    deep_agent = create_deep_agent(
        model=default_model,
        tools=application_tools,
        system_prompt=(
            "You are Big Bear AI, a testing assistant. Produce concrete, verifiable "
            "test designs and use the available application tools when needed."
        ),
        middleware=[inject_runtime_context],
        state_schema=AssistantState,
        name="big_bear_deep_agent",
    )

    async def resolve_context(state: AssistantState) -> dict[str, Any]:
        return {
            "resolved_context": await context_service.resolve(state.get("context"))
        }

    builder = StateGraph(AssistantState)
    builder.add_node("resolve_context", resolve_context)
    builder.add_node("deep_agent", deep_agent)
    builder.add_edge(START, "resolve_context")
    builder.add_edge("resolve_context", "deep_agent")
    builder.add_edge("deep_agent", END)
    return builder.compile(name="assistant")


async def create_graph():
    """LangGraph Agent Server factory."""
    return await asyncio.to_thread(build_assistant_graph)
