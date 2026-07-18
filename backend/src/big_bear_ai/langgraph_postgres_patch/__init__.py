"""`langgraph-api==0.11.1` 的 PostgreSQL 运行时实现。"""

from importlib.metadata import version


_UPSTREAM_API_VERSION = "0.11.1"


def assert_upstream_api_version() -> None:
    installed_version = version("langgraph-api")
    if installed_version != _UPSTREAM_API_VERSION:
        raise RuntimeError(
            "PostgreSQL runtime requires "
            f"langgraph-api=={_UPSTREAM_API_VERSION}; found {installed_version}."
        )


assert_upstream_api_version()

from big_bear_ai.langgraph_postgres_patch import (  # noqa: E402
    checkpoint,
    database,
    lifespan,
    metrics,
    ops,
    queue,
    retry,
    store,
)

__all__ = [
    "assert_upstream_api_version",
    "checkpoint",
    "database",
    "lifespan",
    "metrics",
    "ops",
    "queue",
    "retry",
    "store",
]
