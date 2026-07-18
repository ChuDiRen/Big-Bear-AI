from __future__ import annotations

import argparse
import asyncio

from langgraph_sdk import get_client


def message_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


async def run(url: str, prompt: str) -> str:
    client = get_client(url=url)
    thread = await client.threads.create()
    parts: list[str] = []
    async for chunk in client.runs.stream(
        thread["thread_id"],
        "assistant",
        input={
            "messages": [{"role": "user", "content": prompt}],
            "context": {"mode": "auto"},
        },
        stream_mode=["messages-tuple", "updates", "custom"],
        on_disconnect="cancel",
    ):
        if chunk.event == "messages":
            text = message_text(chunk.data[0])
            if text:
                parts.append(text)
        elif chunk.event == "error":
            raise RuntimeError(str(chunk.data))
    output = "".join(parts).strip()
    if not output:
        raise RuntimeError("assistant stream completed without text")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the real assistant stream")
    parser.add_argument("--url", default="http://127.0.0.1:2024")
    parser.add_argument("--prompt", default="Reply with a short test checklist.")
    args = parser.parse_args()
    print(asyncio.run(run(args.url, args.prompt)))


if __name__ == "__main__":
    main()
