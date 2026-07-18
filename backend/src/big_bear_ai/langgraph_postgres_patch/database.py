import asyncio
import os
import re
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any, TypeAlias

import langgraph_api.config as config
import structlog
from langgraph_api.serde import fragment_loads, json_dumpb
from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg_pool import AsyncConnectionPool
from redis.exceptions import LockError, LockNotOwnedError

from big_bear_ai.langgraph_postgres_patch import redis
from big_bear_ai.langgraph_postgres_patch.redis import LOCK_MIGRATION

Row: TypeAlias = dict[str, Any]


logger = structlog.stdlib.get_logger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_pg_pool: AsyncConnectionPool[AsyncConnection[DictRow]] | None = None
_stats_task: asyncio.Task | None = None

# Thread-local storage for per-thread connection pools
_thread_local = threading.local()


async def healthcheck() -> None:
    # check postgres
    async with connect() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1")
    # check redis
    await redis.get_redis().ping()  # type: ignore[invalid-await]


@asynccontextmanager
async def connect(
    *, supports_core_api: bool = False
) -> AsyncIterator[AsyncConnection[DictRow]]:
    del supports_core_api
    if threading.current_thread() is not threading.main_thread():
        if not hasattr(_thread_local, "pg_pool"):
            _thread_local.pg_pool = create_pool(thread_local=True)
            await _thread_local.pg_pool.open(wait=True)
            logger.info(
                "Created thread-local PostgreSQL connection pool",
                thread_name=threading.current_thread().name,
            )
        async with _thread_local.pg_pool.connection() as conn:
            yield conn
        return

    if _pg_pool is None:
        raise RuntimeError("PostgreSQL pool not initialized")
    async with _pg_pool.connection() as conn:
        yield conn

# noqa  MC80OmFIVnBZMlhsdktEbHY1ZnBtNFE2UkRscWJ3PT06NTZkNGZlZmE=

# Define an configure function that sets JSON adapters for each new connection
async def _configure_connection(conn: AsyncConnection[DictRow]):
    # Register custom JSON dumps/loads on this connection
    set_json_dumps(json_dumpb, conn)
    set_json_loads(fragment_loads, conn)


async def _reset_connection(conn: AsyncConnection[DictRow]) -> None:
    # Always rollback to clear any open transaction or lock
    with suppress(Exception):
        await conn.rollback()
# pragma: no cover  MS80OmFIVnBZMlhsdktEbHY1ZnBtNFE2UkRscWJ3PT06NTZkNGZlZmE=


def create_pool(
    *, thread_local: bool = False
) -> AsyncConnectionPool[AsyncConnection[DictRow]]:
    params = conninfo_to_dict(config.DATABASE_URI)
    params.setdefault("options", "")
    params["options"] += " -c lock_timeout=1000"
    params["options"] += " -c statement_timeout=900s"
    params["options"] += " -c idle_in_transaction_session_timeout=900s"

    # For thread-local pools, use smaller pool sizes
    if thread_local:
        pool_min_size = 1
        # Default to 150 / 10 = 15 to let each worker have equal access to the pool
        pool_max_size = config.POSTGRES_POOL_MAX_SIZE // config.N_JOBS_PER_WORKER
        pool_max_idle = 30
    else:
        pool_min_size = 1
        pool_max_size = config.POSTGRES_POOL_MAX_SIZE
        pool_max_idle = 60

    # create connection pool
    return AsyncConnectionPool(
        connection_class=AsyncConnection[DictRow],
        min_size=pool_min_size,
        max_size=pool_max_size,
        max_idle=pool_max_idle,  # seconds
        timeout=15,
        kwargs={
            **params,
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        configure=_configure_connection,
        reset=_reset_connection,
        open=False,
    )


async def create_conn() -> AsyncConnection[DictRow]:
    params = conninfo_to_dict(config.DATABASE_URI)
    params.setdefault("options", "")
    params["options"] += " -c lock_timeout=1000"
    params["options"] += " -c statement_timeout=900s"
    params["options"] += " -c idle_in_transaction_session_timeout=900s"

    conn = await AsyncConnection.connect(
        config.DATABASE_URI,
        options=params["options"],
        row_factory=dict_row,
        autocommit=True,
        prepare_threshold=0,
    )
    await _configure_connection(conn)
    return conn


def _is_executable(stmt: str) -> bool:
    """去掉前导注释和空白后，判断这条 SQL 是否还有真正的语句要执行。"""
    if not stmt:
        return False
    lines = [ln for ln in stmt.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    return bool(lines)


def _split_sql_statements(sql: str) -> list[str]:
    """按 ; 把迁移 SQL 拆成单条语句，跳过空语句和纯注释。

    支持：
    - 单引号字符串（含 '' 转义）
    - 行注释 --
    - 块注释 /* ... */（不嵌套）
    - dollar-quoted 字符串 $$...$$ 和 $tag$...$tag$（DO 块、函数体常用）

    LangGraph 自带迁移 SQL 用到的就这些，足够。
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        # 单引号字符串
        if ch == "'":
            buf.append(ch)
            i += 1
            while i < n:
                buf.append(sql[i])
                if sql[i] == "'":
                    # '' 是转义的单引号
                    if i + 1 < n and sql[i + 1] == "'":
                        buf.append(sql[i + 1])
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        # 行注释 --
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                buf.append(sql[i])
                i += 1
            continue
        # 块注释 /* ... */
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            buf.append(sql[i])
            buf.append(sql[i + 1])
            i += 2
            while i < n - 1 and not (sql[i] == "*" and sql[i + 1] == "/"):
                buf.append(sql[i])
                i += 1
            if i < n - 1:
                buf.append(sql[i])
                buf.append(sql[i + 1])
                i += 2
            continue
        # dollar-quoted: $tag$...$tag$（tag 可空）
        if ch == "$":
            end_tag = sql.find("$", i + 1)
            if end_tag != -1:
                tag = sql[i : end_tag + 1]  # 形如 "$$" 或 "$func$"
                # 校验 tag 合法（中间只能是 [A-Za-z_][A-Za-z0-9_]*）
                inner = tag[1:-1]
                if inner == "" or (inner[0].isalpha() or inner[0] == "_") and all(
                    c.isalnum() or c == "_" for c in inner
                ):
                    closing = sql.find(tag, end_tag + 1)
                    if closing != -1:
                        buf.append(sql[i : closing + len(tag)])
                        i = closing + len(tag)
                        continue
            # 不是合法的 dollar-quote 开头，当普通字符
            buf.append(ch)
            i += 1
            continue
        # 语句分隔符
        if ch == ";":
            stmt = "".join(buf).strip()
            if _is_executable(stmt):
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if _is_executable(tail):
        statements.append(tail)
    return statements


async def migrate() -> None:
    if not os.path.isdir(config.MIGRATIONS_PATH):
        raise RuntimeError(
            f"PostgreSQL migrations directory is missing: {config.MIGRATIONS_PATH}"
        )
# noqa  Mi80OmFIVnBZMlhsdktEbHY1ZnBtNFE2UkRscWJ3PT06NTZkNGZlZmE=

    async with connect() as conn, conn.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version BIGINT PRIMARY KEY,
                dirty   BOOLEAN NOT NULL
            )
        """)
        await cur.execute(
            "SELECT COALESCE(MAX(version), -1) AS v FROM schema_migrations"
        )
        current_version = (await cur.fetchone())["v"]
        migration_paths: dict[int, str] = {}
        for migration_path in sorted(os.listdir(config.MIGRATIONS_PATH)):
            version = int(migration_path.split("_", 1)[0])
            if not migration_path.endswith(".up.sql"):
                raise ValueError(
                    f"PostgreSQL runtime only accepts standard .up.sql migrations: {migration_path}"
                )
            if version in migration_paths:
                raise ValueError(f"Duplicate PostgreSQL migration version: {version}")
            migration_paths[version] = migration_path

        for version, migration in migration_paths.items():
            if version <= current_version:
                continue
            with open(os.path.join(config.MIGRATIONS_PATH, migration), encoding="utf-8") as f:
                sql = f.read().strip()
            # 按 ; 拆成单条 SQL 分别执行：
            # 1) autocommit=True 时每条独立成一个隐式 transaction
            # 2) CREATE INDEX CONCURRENTLY 不允许在 transaction 里运行，必须单独发
            # 3) 同时跳过空语句和纯注释行，避免给 PG 发空查询
            statements = _split_sql_statements(sql)
            for stmt in statements:
                try:
                    await cur.execute(stmt, prepare=False)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to apply database migration {version}\n\nStatement: {stmt}"
                    ) from e
            await cur.execute(
                "INSERT INTO schema_migrations (version, dirty) VALUES (%s, %s)",
                (version, False),
            )
            logger.info("Applied database migration", version=version)


async def migrate_vector_index():
    from big_bear_ai.langgraph_postgres_patch import store as lg_store

    if not config.STORE_CONFIG:
        return

    config_ = config.STORE_CONFIG
    lg_store.set_store_config(config_)
    logger.info(
        "Setting up vector index",
        store_config=config_,
    )
    await lg_store.setup_vector_index(lg_store.Store())


async def start_pool() -> None:
    global _pg_pool, _stats_task

    # start redis
    # Do this first so we can use redis for locking during migrations
    await redis.start_redis()

    _pg_pool = create_pool()
    # confirm connectivity
    await _pg_pool.open(wait=True)

    # Use redis lock to ensure only one server can run migrations at a time
    # We don't use PG advisory locks cause they result in deadlocks with some of the DDL statements run in migrations
    logger.info("Attempting to acquire migration lock")
    try:
        async with redis.get_redis().lock(
            name=LOCK_MIGRATION,
            timeout=60.0,
            blocking_timeout=30.0,
        ):
            await logger.ainfo("Migration lock acquired")
            # Actually run the migrations
            await migrate()
            await migrate_vector_index()
    except LockError:
        await logger.awarning(
            "Failed to acquire migration lock - another server is already running migrations. Continuing."
        )
    except LockNotOwnedError as e:
        await logger.awarning(
            "Error releasing migration lock. %s Continuing.",
            e,
        )
    except Exception as e:
        await logger.aexception("Migration failed", exc_info=e)
        raise
    finally:
        await logger.ainfo("Migration lock released")

    # start stats loop
    _stats_task = asyncio.create_task(stats_loop())


async def stats_loop() -> None:
    if config.IS_EXECUTOR_ENTRYPOINT:
        return
    _pool = _pg_pool
    if _pool is None:
        raise RuntimeError("Postgres pool not initialized")
    while True:
        logger.info("Postgres pool stats", **_pool.pop_stats())
        await asyncio.sleep(config.STATS_INTERVAL_SECS)


async def stop_pool() -> None:
    global _pg_pool, _stats_task

    if threading.current_thread() is not threading.main_thread():
        # Close thread-local connection pools
        if hasattr(_thread_local, "pg_pool"):
            await _thread_local.pg_pool.close()
            del _thread_local.pg_pool
            logger.info(
                "Closed thread-local Postgres connection pool",
                thread_name=threading.current_thread().name,
            )
        return

    # stop stats loop
    if _stats_task is not None:
        _stats_task.cancel("Stopping pool")
        try:
            await _stats_task
        except asyncio.CancelledError:
            pass
        finally:
            _stats_task = None
    # close main pool (thread-local pools are closed when the thread exits)
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
    # stop redis
    await redis.stop_redis()


def pool_stats(
    project_id: str | None,
    revision_id: str | None,
    format: str = "prometheus",
) -> dict[str, dict[str, int]] | list[str]:
    """Get stats for the main Postgres and Redis pool"""

    # will get exception if start_pool hasn't been called yet
    try:
        stats = {
            "postgres": _get_pool().get_stats(),
            "redis": redis.redis_stats(),
        }
    except Exception:
        return {} if format == "json" else []

    if format == "json":
        return stats

    return [
        "# HELP lg_api_pg_pool_max The maximum size of the postgres connection pool.",
        "# TYPE lg_api_pg_pool_max gauge",
        f'lg_api_pg_pool_max{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"]["pool_max"]}',
        "# HELP lg_api_pg_pool_size Number of connections currently managed by the postgres connection pool (in the pool, given to clients, being prepared)",
        "# TYPE lg_api_pg_pool_size gauge",
        f'lg_api_pg_pool_size{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"]["pool_size"]}',
        "# HELP lg_api_pg_pool_available Number of connections currently idle in the postgres connection pool",
        "# TYPE lg_api_pg_pool_available gauge",
        f'lg_api_pg_pool_available{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"]["pool_available"]}',
        "# HELP lg_api_pg_pool_requests_queued Number of postgres connection requests queued because a postgres connection wasn't immediately available in the pool",
        "# TYPE lg_api_pg_pool_requests_queued counter",
        f'lg_api_pg_pool_requests_queued{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"].get("requests_queued", 0)}',
        "# HELP lg_api_pg_pool_requests_errors Number of postgres connection requests resulting in an error (timeouts, queue full...)",
        "# TYPE lg_api_pg_pool_requests_errors counter",
        f'lg_api_pg_pool_requests_errors{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"].get("requests_errors", 0)}',
        "# HELP lg_api_redis_pool_available Number of connections currently idle in the redis connection pool",
        "# TYPE lg_api_redis_pool_available gauge",
        f'lg_api_redis_pool_available{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["redis"]["idle_connections"]}',
        "# HELP lg_api_redis_pool_size Number of connections currently in use in the redis connection pool",
        "# TYPE lg_api_redis_pool_size gauge",
        f'lg_api_redis_pool_size{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["redis"]["in_use_connections"]}',
        "# HELP lg_api_redis_pool_max The maximum size of the redis connection pool.",
        "# TYPE lg_api_redis_pool_max gauge",
        f'lg_api_redis_pool_max{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["redis"]["max_connections"]}',
    ]


def _get_pool() -> AsyncConnectionPool[AsyncConnection[DictRow]]:
    if threading.current_thread() is not threading.main_thread():
        return _thread_local.pg_pool
    elif _pg_pool is None:
        raise RuntimeError("Postgres pool not initialized")
    else:
        return _pg_pool

# type: ignore  My80OmFIVnBZMlhsdktEbHY1ZnBtNFE2UkRscWJ3PT06NTZkNGZlZmE=

__all__ = [
    "start_pool",
    "stop_pool",
    "connect",
    "pool_stats",
]
