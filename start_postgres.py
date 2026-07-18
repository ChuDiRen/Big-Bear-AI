#!/usr/bin/env python3
"""
Simple LangGraph API Server

A minimal script to start the LangGraph API server directly using uvicorn.
modified according to cli.py under LangGraph API
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
BACKEND_SRC = BACKEND / "src"
VENV_PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 2026

DEFAULT_POSTGRES_URI = "postgresql://postgres@127.0.0.1:5432/big_bear_ai"
DEFAULT_REDIS_URI = "redis://127.0.0.1:6379/0"

# Windows 上 psycopg 异步模式不兼容默认的 ProactorEventLoop，必须切到 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def ensure_backend_venv() -> None:
    if not VENV_PYTHON.is_file():
        raise RuntimeError(f"找不到后端虚拟环境解释器：{VENV_PYTHON}")

    active_python = Path(sys.executable).resolve()
    if active_python != VENV_PYTHON.resolve():
        os.execv(
            str(VENV_PYTHON),
            [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
        )


def listener_pid() -> int | None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex(("127.0.0.1", SERVER_PORT)) != 0:
            return None

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", (
            f"(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort {SERVER_PORT} "
            "-State Listen | Select-Object -First 1 -ExpandProperty OwningProcess)"
        )],
        check=True,
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    return int(output) if output else None


def stop_conflicting_server() -> None:
    pid = listener_pid()
    if pid is None:
        return

    print(f"端口 {SERVER_PORT} 已被进程 {pid} 占用，正在停止其进程树。")
    subprocess.run(["taskkill.exe", "/PID", str(pid), "/T", "/F"], check=True)

    deadline = time.monotonic() + 10
    while listener_pid() is not None:
        if time.monotonic() >= deadline:
            raise RuntimeError(f"等待端口 {SERVER_PORT} 释放超时。")
        time.sleep(0.2)


def configure_project_imports() -> None:
    if not BACKEND_SRC.is_dir():
        raise RuntimeError(f"找不到后端源码目录：{BACKEND_SRC}")

    root_path = ROOT.resolve()
    backend_path = BACKEND_SRC.resolve()
    project_paths = {root_path, backend_path}
    sys.path[:] = [
        entry
        for entry in sys.path
        if Path(entry or os.getcwd()).resolve() not in project_paths
    ]
    sys.path.insert(0, str(backend_path))

    inherited_paths = [
        entry
        for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if entry and Path(entry).resolve() not in project_paths
    ]
    os.environ["PYTHONPATH"] = os.pathsep.join([str(backend_path), *inherited_paths])

    from importlib.metadata import version

    import langgraph_api

    api_path = Path(langgraph_api.__file__).resolve()
    venv_site_packages = VENV_PYTHON.parent.parent / "Lib" / "site-packages"
    if venv_site_packages not in api_path.parents:
        raise RuntimeError(f"langgraph_api 未从后端虚拟环境加载：{api_path}")
    if version("langgraph-api") != "0.11.1":
        raise RuntimeError(
            "PostgreSQL 启动器要求 langgraph-api==0.11.1，"
            f"当前为 {version('langgraph-api')}。"
        )


def load_langgraph_config() -> dict[str, object]:
    config_path = ROOT / "langgraph.json"
    if not config_path.is_file():
        raise RuntimeError(f"找不到 LangGraph 配置文件：{config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"LangGraph 配置不是有效 JSON：{config_path}") from error

    graphs = config.get("graphs")
    if not isinstance(graphs, dict) or not graphs:
        raise RuntimeError("langgraph.json 必须定义非空 graphs")
    if not all(isinstance(name, str) and isinstance(path, str) for name, path in graphs.items()):
        raise RuntimeError("langgraph.json 的 graphs 必须是字符串映射")

    config["graphs"] = {
        name: _resolve_graph_source(path) for name, path in graphs.items()
    }
    return config


def _resolve_graph_source(source: str) -> str:
    path_or_module, separator, export = source.rpartition(":")
    if not separator or not path_or_module or not export:
        raise RuntimeError(f"无效的图定义：{source}")
    if "/" not in path_or_module and "\\" not in path_or_module:
        return source

    graph_path = Path(path_or_module)
    resolved_path = graph_path if graph_path.is_absolute() else ROOT / graph_path
    if not resolved_path.is_file():
        raise RuntimeError(f"图文件不存在：{resolved_path}")
    return f"{resolved_path.resolve().as_posix()}:{export}"


def resolve_connection_uris() -> tuple[str, str]:
    postgres_uri = os.environ.get("BIG_BEAR_POSTGRES_URI") or DEFAULT_POSTGRES_URI
    redis_uri = os.environ.get("BIG_BEAR_REDIS_URI") or DEFAULT_REDIS_URI
    return postgres_uri, redis_uri


def ensure_database(postgres_uri: str) -> None:
    from urllib.parse import urlparse

    import psycopg
    from psycopg import sql

    parsed = urlparse(postgres_uri)
    database_name = parsed.path.lstrip("/")
    if not database_name:
        raise RuntimeError("BIG_BEAR_POSTGRES_URI 必须包含数据库名称")

    connection = psycopg.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
    )
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
                print(f"✅ 已创建 PostgreSQL 数据库：{database_name}")
    finally:
        connection.close()


def setup_environment() -> None:
    """设置 PostgreSQL 持久化运行时所需环境变量。"""
    langgraph_config = load_langgraph_config()
    graphs = langgraph_config["graphs"]
    auth = langgraph_config.get("auth")

    postgres_uri, redis_uri = resolve_connection_uris()
    migrations_path = str(
        (ROOT / "storage" / "migrations").resolve()
    )
    if not Path(migrations_path).is_dir():
        raise RuntimeError(f"找不到 PostgreSQL 迁移目录：{migrations_path}")

    # 创建数据库必须在 LangGraph 运行时读取连接配置之前完成。
    ensure_database(postgres_uri)

    env_vars = {
        # PostgreSQL 运行时优先读取 DATABASE_URI；两个名称必须指向同一实例。
        "DATABASE_URI": postgres_uri,
        "POSTGRES_URI": postgres_uri,
        "REDIS_URI": redis_uri,
        "MIGRATIONS_PATH": migrations_path,
        # 本地 in-memory 无数据库持久化时
        #"DATABASE_URI": ":memory:",
        #"REDIS_URI": "fake",
        #"MIGRATIONS_PATH": "__inmem",

        # Server configuration
        "ALLOW_PRIVATE_NETWORK": "true",
        "LANGGRAPH_UI_BUNDLER": "true",
        "LANGGRAPH_RUNTIME_EDITION": "postgres_local",
        "LANGSMITH_LANGGRAPH_API_VARIANT": "local_dev",
        "LANGGRAPH_DISABLE_FILE_PERSISTENCE": "false",
        "LANGGRAPH_ALLOW_BLOCKING": "true",
        "LANGGRAPH_API_URL": f"http://localhost:{SERVER_PORT}",

        "LANGGRAPH_DEFAULT_RECURSION_LIMIT": "2000",

        # Graphs and auth come only from langgraph.json.
        "LANGSERVE_GRAPHS": json.dumps(graphs),
        "LANGGRAPH_AUTH": json.dumps(auth) if auth is not None else None,

        # Worker configuration
        "N_JOBS_PER_WORKER": "10",
    }
# fmt: off  MS80OmFIVnBZMlhsdktEbHY1ZnBtNFE2TUhWaWJ3PT06YjIzMmFkMDg=

    os.environ.pop("LANGGRAPH_AUTH", None)
    os.environ.update({k: v for k, v in env_vars.items() if v is not None})

def main():
    """Start the server"""
    ensure_backend_venv()
    stop_conflicting_server()
    configure_project_imports()
    os.chdir(BACKEND)

    print("🚀 Starting Simple LangGraph API Server...")

    # Setup environment
    setup_environment()

    # Print server information
    print("\n" + "="*60)
    print(f"📍 Server URL: http://localhost:{SERVER_PORT}")
    print(f"📚 API Documentation: http://localhost:{SERVER_PORT}/docs")
    print(f"🎨 Studio UI: http://localhost:{SERVER_PORT}/ui")
    print(f"💚 Health Check: http://localhost:{SERVER_PORT}/ok")
    print("="*60)

    try:
        # Import uvicorn after environment setup
        import uvicorn
# pylint: disable  Mi80OmFIVnBZMlhsdktEbHY1ZnBtNFE2TUhWaWJ3PT06YjIzMmFkMDg=

        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
            "loggers": {
                "uvicorn": {"level": "INFO"},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"level": "WARNING"},
            }
        }

        # 用 Config + Server + asyncio.run(loop_factory=...) 显式控制事件循环，
        # 避免 uvicorn.run 在 Windows 上把循环重置回 ProactorEventLoop
        config = uvicorn.Config(
            "langgraph_api.server:app",
            host=SERVER_HOST,
            port=SERVER_PORT,
            reload=False,
            access_log=False,
            loop="asyncio",
            log_config=log_config,
        )
        server = uvicorn.Server(config)
# pragma: no cover  My80OmFIVnBZMlhsdktEbHY1ZnBtNFE2TUhWaWJ3PT06YjIzMmFkMDg=

        asyncio.run(server.serve())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
