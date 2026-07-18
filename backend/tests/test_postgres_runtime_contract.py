from __future__ import annotations

import inspect
import os


os.environ.setdefault(
    "DATABASE_URI", "postgresql://postgres:postgres@127.0.0.1:5432/langgraph"
)
os.environ.setdefault("POSTGRES_URI", os.environ["DATABASE_URI"])
os.environ.setdefault("REDIS_URI", "redis://127.0.0.1:6379/0")
os.environ.setdefault("MIGRATIONS_PATH", "storage/migrations")


def test_postgres_runtime_uses_current_public_operation_contracts() -> None:
    from langgraph_runtime_inmem import ops as official_ops

    from big_bear_ai.langgraph_postgres_patch import ops as postgres_ops

    for resource_name in ("Assistants", "Threads", "Runs", "Crons"):
        official_resource = getattr(official_ops, resource_name)
        postgres_resource = getattr(postgres_ops, resource_name)

        for operation_name in dir(official_resource):
            official_operation = getattr(official_resource, operation_name)
            postgres_operation = getattr(postgres_resource, operation_name, None)
            if (
                operation_name.startswith("_")
                or not callable(official_operation)
                or not callable(postgres_operation)
            ):
                continue

            official_parameters = inspect.signature(official_operation).parameters
            postgres_parameters = inspect.signature(postgres_operation).parameters
            assert tuple(postgres_parameters) == tuple(official_parameters)
            assert [
                (parameter.kind, parameter.default)
                for parameter in postgres_parameters.values()
            ] == [
                (parameter.kind, parameter.default)
                for parameter in official_parameters.values()
            ]


def test_postgres_runtime_entrypoint_has_no_intermediate_bridge() -> None:
    from big_bear_ai.langgraph_postgres_patch import ops as postgres_ops
    from langgraph_runtime_postgres_local import ops as runtime_ops

    assert runtime_ops is postgres_ops