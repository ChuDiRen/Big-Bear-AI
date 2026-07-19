from __future__ import annotations

import json
from pathlib import Path


def test_root_langgraph_config_exports_both_graphs() -> None:
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "langgraph.json").read_text(encoding="utf-8"))

    assert config["dependencies"] == ["./backend"]
    assert config["graphs"] == {
        "assistant": "./backend/src/big_bear_ai/graphs/assistant.py:create_graph",
        "management": "./backend/src/big_bear_ai/graphs/management.py:graph",
    }
    assert config["auth"] == {
        "path": "big_bear_ai.auth.langgraph:auth",
        "disable_studio_auth": True,
    }
    assert config["http"]["app"] == "big_bear_ai.auth.http:app"
    assert set(config["http"]["cors"]["allow_origins"]) == {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }

