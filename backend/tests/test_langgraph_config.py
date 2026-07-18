from __future__ import annotations

import json
from pathlib import Path


def test_root_langgraph_config_exports_both_graphs() -> None:
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "langgraph.json").read_text(encoding="utf-8"))

    assert config["dependencies"] == ["./Backend"]
    assert config["graphs"] == {
        "assistant": "./Backend/src/big_bear_ai/graphs/assistant.py:create_graph",
        "management": "./Backend/src/big_bear_ai/graphs/management.py:graph",
    }
    assert config["env"] == ".env"
    assert set(config["http"]["cors"]["allow_origins"]) == {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }

