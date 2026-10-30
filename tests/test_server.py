import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from google.api_core.exceptions import BadRequest, Forbidden
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from flin_bigquery_mcp import server


@pytest.mark.parametrize(
    "exc",
    [
        BadRequest("secret query"),
        Forbidden("secret token"),
        RuntimeError("secret credentials"),
    ],
)
def test_error_messages_are_sanitized(exc):
    assert "secret" not in str(server.tool_error(exc))


def test_stdio_protocol_and_tool_validation():
    async def check():
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GOOGLE_")
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "flin_bigquery_mcp.server"],
            env=env,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                assert set(tools) == {
                    "health_check",
                    "list_projects",
                    "list_datasets",
                    "get_dataset",
                    "list_tables",
                    "get_table",
                    "preview_table",
                    "dry_run_query",
                    "run_query",
                    "get_query_results",
                }
                assert tools["run_query"].annotations.readOnlyHint is False
                assert tools["run_query"].annotations.idempotentHint is False
                assert tools["get_table"].annotations.readOnlyHint is True
                result = await session.call_tool("health_check", {})
                assert not result.isError
                payload = json.loads(result.content[0].text)
                assert payload["status"] == "missing_configuration"
                for size in (0, 1001):
                    invalid = await session.call_tool(
                        "list_projects", {"page_size": size}
                    )
                    assert invalid.isError
                invalid = await session.call_tool(
                    "run_query", {"sql": "SELECT 1", "maximum_bytes_billed": 0}
                )
                assert invalid.isError

    asyncio.run(check())
