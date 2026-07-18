from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from big_bear_ai.config import Settings, load_settings
from big_bear_ai.database import Database
from big_bear_ai.services.management import ErrorPayload, ManagementService


class ManagementState(TypedDict, total=False):
    operation: str
    resource: str
    resource_id: str
    query: dict[str, Any]
    payload: dict[str, Any]
    ok: bool
    data: Any
    error: ErrorPayload | None


class ManagementInput(TypedDict, total=False):
    operation: str
    resource: str
    resource_id: str
    query: dict[str, Any]
    payload: dict[str, Any]


class ManagementOutput(TypedDict):
    ok: bool
    data: Any
    error: ErrorPayload | None


def build_management_graph(settings: Settings | None = None):
    active_settings = settings or load_settings()
    service = ManagementService(Database(active_settings.database_path), active_settings)

    async def dispatch(state: ManagementState) -> ManagementOutput:
        return await service.handle(dict(state))

    builder = StateGraph(
        ManagementState,
        input_schema=ManagementInput,
        output_schema=ManagementOutput,
    )
    builder.add_node("dispatch", dispatch)
    builder.add_edge(START, "dispatch")
    builder.add_edge("dispatch", END)
    return builder.compile(name="management")


graph = build_management_graph()
