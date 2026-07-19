from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_start_script_selects_runtime_and_injects_backend_target() -> None:
    script = (ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "ValidateSet('inmem', 'postgres')" in script
    assert "[string]$Runtime = 'inmem'" in script
    assert "[int]$BackendPort = 2026" in script
    assert "start_postgres.py" in script
    assert "start__inmem.py" in script
    assert "BIG_BEAR_SERVER_PORT" in script
    assert "VITE_LANGGRAPH_PROXY_TARGET" in script
    assert "Start-Process -FilePath $backendPython" in script
    assert "Start-Process -FilePath 'pnpm.cmd'" in script
    assert "backend.pid" in script
    assert "frontend.pid" in script
    assert "Invoke-WebRequest" in script
    assert "TotalSeconds" in script
    assert "StartTimeUtcTicks" in script
    assert "DateTime]::Parse" not in script
    assert "langgraph dev" not in script
    assert ".langgraph_api" not in script


def test_postgres_launcher_uses_local_python_postgres_runtime() -> None:
    script = (ROOT / "start_postgres.py").read_text(encoding="utf-8")

    assert '"LANGGRAPH_RUNTIME_EDITION": "postgres_local"' in script
    assert 'version("langgraph-api") != "0.11.1"' in script
    assert 'os.environ.get("BIG_BEAR_SERVER_PORT", "2026")' in script
    assert "load_dotenv(ROOT / \".env\", override=False)" in script
    assert 'os.environ.get("DATABASE_URI")' in script
    assert 'os.environ.get("REDIS_URI")' in script
    assert '"BIG_BEAR_RUNTIME": "postgres"' in script
    assert '"LANGGRAPH_HTTP": json.dumps(http)' in script


def test_inmem_launcher_accepts_the_orchestrated_port() -> None:
    script = (ROOT / "start__inmem.py").read_text(encoding="utf-8")

    assert 'os.environ.get("BIG_BEAR_SERVER_PORT", "2026")' in script
    assert '"BIG_BEAR_RUNTIME": "inmem"' in script
    assert '"LANGGRAPH_HTTP": json.dumps(http)' in script


def test_stop_script_uses_recorded_pids_instead_of_killing_port_owners() -> None:
    script = (ROOT / "stop.ps1").read_text(encoding="utf-8")

    assert "backend.pid" in script
    assert "frontend.pid" in script
    assert "Get-NetTCPConnection" not in script
    assert "OwningProcess" not in script
    assert "TotalSeconds" in script
    assert "StartTimeUtcTicks" in script
    assert "DateTime]::Parse" not in script
