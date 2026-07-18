import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Any

import structlog
from langchain_core.runnables.config import RunnableConfig, var_child_runnable_config
from langgraph.constants import CONF
from starlette.applications import Starlette

from big_bear_ai.langgraph_postgres_patch import checkpoint, database, queue

logger = structlog.stdlib.get_logger(__name__)
_LAST_LIFESPAN_ERROR: BaseException | None = None


def get_last_error() -> BaseException | None:
    return _LAST_LIFESPAN_ERROR


@asynccontextmanager
async def lifespan(
    app: Starlette | None = None,
    cancel_event: asyncio.Event | None = None,
    taskset: set[asyncio.Task] | None = None,
    **kwargs: Any,
):
    from langgraph_api import __version__, feature_flags, graph
    from langgraph_api import _checkpointer as api_checkpointer
    from langgraph_api import config
    from langgraph_api import store as api_store
    from langgraph_api.asyncio import SimpleTaskGroup, set_event_loop
    from langgraph_api.http import (
        start_http_client,
        stop_http_client,
        stop_webhook_http_client,
    )
    from langgraph_api.js.ui import start_ui_bundler, stop_ui_bundler
    from langgraph_api.metadata import metadata_loop
    from langgraph_api.metrics_otlp import (
        COUNTER_SERVER_REQUESTED_TO_STOP,
        COUNTER_SERVER_STARTED,
        COUNTER_SERVER_STOPPED,
        get_otlp_metrics_reporter,
    )

    global _LAST_LIFESPAN_ERROR
    _LAST_LIFESPAN_ERROR = None
    await logger.ainfo(
        "Starting Big Bear PostgreSQL runtime",
        langgraph_api_version=__version__,
        postgres_runtime_version="0.1.0",
    )

    try:
        set_event_loop(asyncio.get_running_loop())
    except RuntimeError:
        await logger.aerror("Failed to set event loop")

    await start_http_client()
    await database.start_pool()
    await checkpoint.start_checkpoint_ingestion_loop()
    await api_checkpointer.start_checkpointer()
    await start_ui_bundler()

    reporter = get_otlp_metrics_reporter()
    reporter.initialize()
    reporter.inc_counter(COUNTER_SERVER_STARTED)

    try:
        async with SimpleTaskGroup(
            cancel=True,
            cancel_event=cancel_event,
            taskgroup_name="PostgresLifespan",
        ) as tg:
            tg.create_task(metadata_loop())
            from langgraph_api.metrics_collector import collector_loop

            tg.create_task(collector_loop())
            await api_store.collect_store_from_env()
            store_instance = await api_store.get_store()
            if not api_store.CUSTOM_STORE:
                tg.create_task(store_instance.start_ttl_sweeper())
            if config.THREAD_TTL:
                tg.create_task(thread_ttl_sweep_loop(config.THREAD_TTL))

            if feature_flags.USE_RUNTIME_CONTEXT_API:
                from langgraph._internal._constants import CONFIG_KEY_RUNTIME
                from langgraph.runtime import Runtime

                runtime_config: RunnableConfig = {
                    CONF: {CONFIG_KEY_RUNTIME: Runtime(store=store_instance)}
                }
            else:
                from langgraph.constants import CONFIG_KEY_STORE

                runtime_config = {CONF: {CONFIG_KEY_STORE: store_instance}}
            var_child_runnable_config.set(runtime_config)

            graph.patch_packages_distributions()
            await graph.collect_graphs_from_env(True)

            if config.N_JOBS_PER_WORKER > 0:
                tg.create_task(queue_with_signal())

            from langgraph_api import cron_scheduler

            tg.create_task(cron_scheduler.cron_scheduler())
            yield
    except graph.GraphLoadError as exc:
        _LAST_LIFESPAN_ERROR = exc
        raise
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        _LAST_LIFESPAN_ERROR = exc
        logger.exception("PostgreSQL runtime lifespan failed", exc_info=exc)
        raise
    finally:
        reporter.inc_counter(COUNTER_SERVER_REQUESTED_TO_STOP)
        await api_store.exit_store()
        await api_checkpointer.exit_checkpointer()
        await stop_ui_bundler()
        await graph.stop_remote_graphs()
        await stop_http_client()
        await stop_webhook_http_client()
        await checkpoint.stop_checkpoint_ingestion_loop()
        await database.stop_pool()
        reporter.inc_counter(COUNTER_SERVER_STOPPED)
        reporter.shutdown()


async def thread_ttl_sweep_loop(ttl_config: dict[str, Any]) -> None:
    interval_seconds = float(ttl_config.get("sweep_interval_minutes", 5)) * 60
    while True:
        try:
            async with database.connect() as conn:
                result = await ops.Threads.sweep_ttl(conn)
                await logger.ainfo(
                    "Thread TTL sweep completed",
                    expired=result.expired,
                    deleted=result.deleted,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await logger.aexception("Thread TTL sweep failed", exc_info=exc)
        await asyncio.sleep(interval_seconds)


async def queue_with_signal() -> None:
    try:
        await queue.queue()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.exception("Queue failed. Signaling shutdown", exc_info=exc)
        signal.raise_signal(signal.SIGINT)


lifespan.get_last_error = get_last_error  # type: ignore[attr-defined]