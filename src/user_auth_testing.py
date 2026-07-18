import asyncio
# type: ignore  MC8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2UkhaVlVBPT06ZjliZDE3ZjI=

from langgraph_sdk import get_client
async def main():
    # Try without a token (should fail)
    # client = get_client(url="http://localhost:2026")
    # try:
    #     thread = await client.threads.create()
    #     print("❌ Should have failed without token!")
    # except Exception as e:
    #     print("✅ Correctly blocked access:", e)

    # Try with a valid token
    client = get_client(
        url="http://localhost:2026", headers={"Authorization": "Bearer user1-token"}
    )

    # Create a thread and chat
    thread = await client.threads.create()
    print(f"✅ Created thread as Alice: {thread['thread_id']}")
# noqa  MS8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2UkhaVlVBPT06ZjliZDE3ZjI=

    response = await client.runs.create(
        thread_id=thread["thread_id"],
        assistant_id="chat_agent",
        input={"messages": [{"role": "user", "content": "Hello!"}]},
    )
    print("✅ Bot responded:")
    print(response)

asyncio.run(main())