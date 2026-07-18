#!/usr/bin/env python3
"""以 LangGraph 内存运行时启动支持热加载的 Big Bear AI 后端。"""

from __future__ import annotations

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
HOST = "127.0.0.1"
PORT = 2026


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
        if probe.connect_ex((HOST, PORT)) != 0:
            return None

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", (
            f"(Get-NetTCPConnection -LocalAddress {HOST} -LocalPort {PORT} "
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

    print(f"端口 {PORT} 已被进程 {pid} 占用，正在停止其进程树。")
    subprocess.run(["taskkill.exe", "/PID", str(pid), "/T", "/F"], check=True)

    deadline = time.monotonic() + 10
    while listener_pid() is not None:
        if time.monotonic() >= deadline:
            raise RuntimeError(f"等待端口 {PORT} 释放超时。")
        time.sleep(0.2)


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


def configure_environment() -> None:
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
            "内存启动器要求 langgraph-api==0.11.1，"
            f"当前为 {version('langgraph-api')}。"
        )

    langgraph_config = load_langgraph_config()
    graphs = langgraph_config["graphs"]
    auth = langgraph_config.get("auth")

    os.environ.pop("LANGGRAPH_AUTH", None)
    os.environ.update(
        {
            "DATABASE_URI": ":memory:",
            "REDIS_URI": "fake",
            "MIGRATIONS_PATH": "__inmem",
            "ALLOW_PRIVATE_NETWORK": "true",
            "LANGGRAPH_UI_BUNDLER": "true",
            "LANGGRAPH_RUNTIME_EDITION": "inmem",
            "LANGSMITH_LANGGRAPH_API_VARIANT": "local_dev",
            "LANGGRAPH_DISABLE_FILE_PERSISTENCE": "true",
            "LANGGRAPH_ALLOW_BLOCKING": "true",
            "LANGGRAPH_API_URL": f"http://{HOST}:{PORT}",
            "LANGSERVE_GRAPHS": json.dumps(graphs),
            "N_JOBS_PER_WORKER": "1",
            **(
                {"LANGGRAPH_AUTH": json.dumps(auth)}
                if auth is not None
                else {}
            ),
        }
    )


def main() -> None:
    ensure_backend_venv()
    stop_conflicting_server()
    configure_environment()
    os.chdir(BACKEND)

    import uvicorn

    print(f"启动 Big Bear AI 内存模式：http://{HOST}:{PORT}")
    print(f"API 文档：http://{HOST}:{PORT}/docs")
    print("图：assistant、management")
    print("已开启热加载，监听 backend/ 目录的代码变更。")

    uvicorn.run(
        "langgraph_api.server:app",
        host=HOST,
        port=PORT,
        reload=True,
        reload_dirs=[str(BACKEND)],
        access_log=False,
        log_level="info",
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    except Exception as error:
        print(f"启动失败：{error}", file=sys.stderr)
        raise