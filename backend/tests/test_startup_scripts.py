from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_start_script_launches_both_development_servers_and_records_ownership() -> None:
    script = (ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "--no-browser" in script
    assert "--config" in script
    assert "langgraph.json" in script
    assert "Start-Process -FilePath $backendFile" in script
    assert "Start-Process -FilePath 'pnpm'" in script
    assert "backend.pid" in script
    assert "frontend.pid" in script
    assert "Invoke-WebRequest" in script
    assert "TotalSeconds" in script
    assert "StartTimeUtcTicks" in script
    assert "DateTime]::Parse" not in script
    assert "Reset-LangGraphRuntime" in script
    assert ".langgraph_api" in script
    assert "Remove-Item -LiteralPath $langGraphRuntime" in script
    assert "New-Item -ItemType Directory -Path $langGraphRuntime -Force" in script


def test_postgres_launcher_uses_local_python_postgres_runtime() -> None:
    script = (ROOT / "start_postgres.py").read_text(encoding="utf-8")

    assert '"LANGGRAPH_RUNTIME_EDITION": "postgres_local"' in script
    assert 'version("langgraph-api") != "0.11.1"' in script


def test_stop_script_uses_recorded_pids_instead_of_killing_port_owners() -> None:
    script = (ROOT / "stop.ps1").read_text(encoding="utf-8")

    assert "backend.pid" in script
    assert "frontend.pid" in script
    assert "Get-NetTCPConnection" not in script
    assert "OwningProcess" not in script
    assert "TotalSeconds" in script
    assert "StartTimeUtcTicks" in script
    assert "DateTime]::Parse" not in script
