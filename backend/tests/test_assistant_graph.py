from __future__ import annotations

from pathlib import Path
import inspect
from typing import Any, Sequence

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class ScriptedToolModel(BaseChatModel):
    responses: list[AIMessage]
    response_index: int = 0
    seen_messages: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tool_names: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-model"

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen_messages.append(list(messages))
        response = self.responses[self.response_index]
        self.response_index += 1
        return ChatResult(generations=[ChatGeneration(message=response)])


def settings_for(tmp_path: Path):
    from big_bear_ai.config import load_settings

    return load_settings(
        {"BIG_BEAR_DATA_DIR": str(tmp_path), "LANGSMITH_TRACING": "false"}
    )


def test_agent_server_factory_is_async_to_avoid_blocking_event_loop() -> None:
    from big_bear_ai.graphs.assistant import create_graph

    assert inspect.iscoroutinefunction(create_graph)


@pytest.mark.asyncio
async def test_assistant_preserves_deep_agent_prompt_and_binds_application_tools(
    tmp_path: Path,
) -> None:
    from big_bear_ai.graphs.assistant import build_assistant_graph

    model = ScriptedToolModel(responses=[AIMessage(content="Ready to test.")])
    graph = build_assistant_graph(settings_for(tmp_path), model=model)

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "Help me test checkout"}]}
    )

    assert result["messages"][-1].text == "Ready to test."
    system_text = "\n".join(
        message.text for message in model.seen_messages[0] if message.type == "system"
    )
    assert "You are a deep agent" in system_text
    assert "Big Bear AI runtime context" in system_text
    assert {
        "search_knowledge",
        "call_plugin",
        "list_mcp_tools",
        "call_mcp_tool",
        "save_test_design",
    } <= set(model.bound_tool_names)


@pytest.mark.asyncio
async def test_assistant_injects_selected_project_agent_and_rule_context(
    tmp_path: Path,
) -> None:
    from big_bear_ai.database import Database
    from big_bear_ai.graphs.assistant import build_assistant_graph
    from big_bear_ai.repositories.resources import ResourceRepository

    settings = settings_for(tmp_path)
    database = Database(settings.database_path)
    await database.initialize()
    repository = ResourceRepository(database)
    project = await repository.create(
        "project", {"name": "Checkout", "description": "Payment API"}
    )
    rule = await repository.create(
        "rule",
        {
            "title": "Contract checks",
            "description": "",
            "definition": "Validate every response schema.",
        },
    )
    agent = await repository.create(
        "agent",
        {
            "name": "API specialist",
            "description": "",
            "instructions": "Prioritize negative API cases.",
            "allowed_rule_ids": [rule["id"]],
            "allowed_document_ids": [],
            "allowed_plugin_ids": [],
        },
    )
    model = ScriptedToolModel(responses=[AIMessage(content="Context loaded.")])
    graph = build_assistant_graph(settings, model=model)

    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": "Design tests"}],
            "context": {
                "mode": "design",
                "project_id": project["id"],
                "agent_id": agent["id"],
            },
        }
    )

    system_text = "\n".join(
        message.text for message in model.seen_messages[0] if message.type == "system"
    )
    assert "Mode: design" in system_text
    assert "Project: Checkout" in system_text
    assert "Agent: API specialist" in system_text
    assert "Prioritize negative API cases." in system_text
    assert "Validate every response schema." in system_text
    assert result["resolved_context"]["project"]["id"] == project["id"]


@pytest.mark.asyncio
async def test_assistant_uses_selected_agent_model_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from big_bear_ai.database import Database
    from big_bear_ai.graphs import assistant as assistant_module
    from big_bear_ai.repositories.resources import ResourceRepository

    settings = settings_for(tmp_path)
    database = Database(settings.database_path)
    await database.initialize()
    agent = await ResourceRepository(database).create(
        "agent",
        {
            "name": "Override model agent",
            "instructions": "Use the selected model.",
            "model_override": "test:override-model",
        },
    )
    default_model = ScriptedToolModel(
        responses=[AIMessage(content="Default model response")]
    )
    override_model = ScriptedToolModel(
        responses=[AIMessage(content="Override model response")]
    )
    requested_models: list[str | None] = []

    def model_factory(_settings, model_name=None):
        requested_models.append(model_name)
        return override_model if model_name == "test:override-model" else default_model

    monkeypatch.setattr(assistant_module, "create_chat_model", model_factory)
    graph = assistant_module.build_assistant_graph(settings)

    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": "Use my agent"}],
            "context": {"agent_id": agent["id"]},
        }
    )

    assert requested_models == [None, "test:override-model"]
    assert result["messages"][-1].text == "Override model response"
    assert override_model.seen_messages


@pytest.mark.asyncio
async def test_assistant_renders_selected_prompt_variables(tmp_path: Path) -> None:
    from big_bear_ai.database import Database
    from big_bear_ai.graphs.assistant import build_assistant_graph
    from big_bear_ai.repositories.resources import ResourceRepository

    settings = settings_for(tmp_path)
    database = Database(settings.database_path)
    await database.initialize()
    prompt = await ResourceRepository(database).create(
        "prompt",
        {
            "title": "API prompt",
            "template": "Test {target} against {schema}.",
            "variables": ["target", "schema"],
        },
    )
    model = ScriptedToolModel(responses=[AIMessage(content="Prompt rendered.")])
    graph = build_assistant_graph(settings, model=model)

    await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": "Design tests"}],
            "context": {
                "prompt_id": prompt["id"],
                "prompt_variables": {
                    "target": "checkout API",
                    "schema": "OpenAPI contract",
                },
            },
        }
    )

    system_text = "\n".join(
        message.text for message in model.seen_messages[0] if message.type == "system"
    )
    assert "Test checkout API against OpenAPI contract." in system_text
    assert "{target}" not in system_text
    assert "{schema}" not in system_text


@pytest.mark.asyncio
async def test_assistant_executes_knowledge_tool_with_agent_scope(tmp_path: Path) -> None:
    from big_bear_ai.database import Database
    from big_bear_ai.graphs.assistant import build_assistant_graph
    from big_bear_ai.repositories.resources import ResourceRepository
    from big_bear_ai.services.documents import DocumentService

    import base64

    settings = settings_for(tmp_path)
    database = Database(settings.database_path)
    await database.initialize()
    document = await DocumentService(database, settings).upload(
        {
            "filename": "guide.txt",
            "content_base64": base64.b64encode(
                b"Boundary value analysis covers values just inside and outside limits."
            ).decode("ascii"),
        }
    )
    agent = await ResourceRepository(database).create(
        "agent",
        {
            "name": "Knowledge agent",
            "description": "",
            "instructions": "Use the knowledge base.",
            "allowed_document_ids": [document["id"]],
            "allowed_rule_ids": [],
            "allowed_plugin_ids": [],
        },
    )
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "Boundary value"},
                        "id": "call-knowledge",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="I found the guide."),
        ]
    )
    graph = build_assistant_graph(settings, model=model)

    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": "Find boundary guidance"}],
            "context": {"agent_id": agent["id"]},
        }
    )

    tool_messages = [
        message for message in model.seen_messages[1] if message.type == "tool"
    ]
    assert "outside limits" in tool_messages[-1].text
    assert result["messages"][-1].text == "I found the guide."


@pytest.mark.asyncio
async def test_assistant_uses_the_rule_selected_by_home_context(tmp_path: Path) -> None:
    from big_bear_ai.database import Database
    from big_bear_ai.graphs.assistant import build_assistant_graph
    from big_bear_ai.repositories.resources import ResourceRepository

    settings = settings_for(tmp_path)
    database = Database(settings.database_path)
    await database.initialize()
    repository = ResourceRepository(database)
    selected_rule = await repository.create(
        "rule",
        {
            "title": "Selected boundary rule",
            "definition": "Prioritize boundary values.",
        },
    )
    await repository.create(
        "rule",
        {
            "title": "Unselected performance rule",
            "definition": "Prioritize load testing.",
        },
    )
    model = ScriptedToolModel(responses=[AIMessage(content="Rule loaded.")])
    graph = build_assistant_graph(settings, model=model)

    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": "Design tests"}],
            "context": {"rule_id": selected_rule["id"]},
        }
    )

    system_text = "\n".join(
        message.text for message in model.seen_messages[0] if message.type == "system"
    )
    assert "Selected boundary rule" in system_text
    assert "Unselected performance rule" not in system_text
    assert result["resolved_context"]["rule"]["id"] == selected_rule["id"]
