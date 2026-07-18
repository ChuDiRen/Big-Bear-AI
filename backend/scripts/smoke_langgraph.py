from __future__ import annotations

import argparse
import asyncio
import base64
import json
from contextlib import suppress
from uuid import uuid4

from langgraph_sdk import get_client


async def manage(client, request: dict) -> object:
    result = await client.runs.wait(
        None,
        "management",
        input=request,
        on_disconnect="cancel",
        raise_error=True,
    )
    if not result.get("ok"):
        error = result.get("error") or {}
        raise RuntimeError(
            f"{error.get('code', 'UNKNOWN')}: {error.get('message', 'management failed')}"
        )
    return result["data"]


async def run_smoke(url: str) -> dict[str, object]:
    client = get_client(url=url)
    suffix = uuid4().hex[:8]
    created: list[tuple[str, str]] = []
    plugin_installed = False
    summary: dict[str, object] = {"url": url}

    try:
        project = await manage(
            client,
            {
                "operation": "create",
                "resource": "project",
                "payload": {
                    "name": f"Smoke Project {suffix}",
                    "description": "LangGraph API smoke test",
                },
            },
        )
        created.append(("project", project["id"]))

        design = await manage(
            client,
            {
                "operation": "create",
                "resource": "design",
                "payload": {
                    "project_id": project["id"],
                    "title": f"Smoke Design {suffix}",
                    "content": "Verify the checkout boundary cases.",
                },
            },
        )
        created.append(("design", design["id"]))

        rule = await manage(
            client,
            {
                "operation": "create",
                "resource": "rule",
                "payload": {
                    "title": f"Smoke Rule {suffix}",
                    "definition": "Check every boundary value.",
                    "tags": ["smoke"],
                },
            },
        )
        created.append(("rule", rule["id"]))

        prompt = await manage(
            client,
            {
                "operation": "create",
                "resource": "prompt",
                "payload": {
                    "title": f"Smoke Prompt {suffix}",
                    "template": "Design tests for {target}",
                    "variables": ["target"],
                },
            },
        )
        created.append(("prompt", prompt["id"]))

        document = await manage(
            client,
            {
                "operation": "action",
                "resource": "document",
                "payload": {
                    "action": "upload",
                    "filename": f"smoke-{suffix}.txt",
                    "content_base64": base64.b64encode(
                        b"Smoke retrieval checks the checkout boundary behavior."
                    ).decode("ascii"),
                },
            },
        )
        created.append(("document", document["id"]))
        search = await manage(
            client,
            {
                "operation": "action",
                "resource": "document",
                "payload": {"action": "search", "query": "checkout boundary"},
            },
        )
        if not any(item["document_id"] == document["id"] for item in search):
            raise RuntimeError("uploaded document was not retrievable")

        agent = await manage(
            client,
            {
                "operation": "create",
                "resource": "agent",
                "payload": {
                    "name": f"Smoke Agent {suffix}",
                    "instructions": "Use the selected smoke resources.",
                    "allowed_rule_ids": [rule["id"]],
                    "allowed_document_ids": [document["id"]],
                    "allowed_plugin_ids": ["data-generator"],
                },
            },
        )
        created.append(("agent", agent["id"]))

        await manage(
            client,
            {
                "operation": "action",
                "resource": "plugin",
                "payload": {
                    "action": "install",
                    "plugin_id": "data-generator",
                },
            },
        )
        plugin_installed = True
        plugin_result = await manage(
            client,
            {
                "operation": "action",
                "resource": "plugin",
                "payload": {
                    "action": "call",
                    "plugin_id": "data-generator",
                    "input": {
                        "count": 2,
                        "schema": {"name": "string", "attempt": "integer"},
                    },
                },
            },
        )
        if plugin_result != [
            {"name": "sample-1", "attempt": 1},
            {"name": "sample-2", "attempt": 2},
        ]:
            raise RuntimeError("plugin call returned unexpected data")

        project_page = await manage(
            client,
            {
                "operation": "list",
                "resource": "project",
                "query": {"search": suffix, "limit": 100},
            },
        )
        if not any(item["id"] == project["id"] for item in project_page["items"]):
            raise RuntimeError("created project was not listed")

        summary.update(
            {
                "project_id": project["id"],
                "design_id": design["id"],
                "document_id": document["id"],
                "retrieval_hits": len(search),
                "plugin_result_count": len(plugin_result),
            }
        )
        return summary
    finally:
        if plugin_installed:
            with suppress(Exception):
                await manage(
                    client,
                    {
                        "operation": "action",
                        "resource": "plugin",
                        "payload": {
                            "action": "uninstall",
                            "plugin_id": "data-generator",
                        },
                    },
                )
        for resource, resource_id in reversed(created):
            with suppress(Exception):
                await manage(
                    client,
                    {
                        "operation": "delete",
                        "resource": resource,
                        "resource_id": resource_id,
                    },
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the Big Bear LangGraph API")
    parser.add_argument("--url", default="http://127.0.0.1:2024")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_smoke(args.url)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
