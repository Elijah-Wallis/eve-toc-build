#!/usr/bin/env python3
import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOL_NAME = "update_tasks"
TEST_ARGS = {
  "id": "eq.7944c4c3-5e8c-4987-a4cc-cc16f8cdc3a9",
  "status": "eq.queued"
}


async def main() -> None:
    server_dir = Path(__file__).resolve().parent
    params = StdioServerParameters(
        command="node",
        args=["dist/index.js"],
        cwd=str(server_dir),
        env=dict(os.environ),
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print("TOOLS")
                print(json.dumps(tools.model_dump(), indent=2, default=str))
                result = await session.call_tool(TOOL_NAME, arguments=TEST_ARGS)
                print("RESULT")
                print(json.dumps(result.model_dump(), indent=2, default=str))
    except Exception as exc:  # pylint: disable=broad-except
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
