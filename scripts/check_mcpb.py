"""Exercise the actual desktop bundle through its manifest command, without Google access."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
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


async def verify_server(parameters: StdioServerParameters) -> None:
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=180)
        ) as client:
            await client.initialize()
            response = await client.list_tools()
            assert {tool.name for tool in response.tools} == EXPECTED_TOOLS
            for tool in response.tools:
                assert tool.annotations and tool.annotations.title
                assert tool.annotations.readOnlyHint is (tool.name != "run_query")
                assert tool.annotations.idempotentHint is (tool.name != "run_query")
                assert tool.annotations.destructiveHint is False
                assert tool.annotations.openWorldHint is (tool.name != "health_check")
            health = await client.call_tool("health_check", {})
            assert not health.isError
            assert health.structuredContent["status"] == "oauth_required"
            assert health.structuredContent["default_project"] == "smoke-project"
            assert health.structuredContent["maximum_bytes_billed"] == 1073741824
            invalid = await client.call_tool("list_projects", {"page_size": 0})
            assert invalid.isError
            invalid = await client.call_tool(
                "run_query", {"sql": "SELECT 1", "maximum_bytes_billed": 0}
            )
            assert invalid.isError


async def check_bundle(bundle: Path) -> None:
    if bundle.is_dir():
        candidates = list(bundle.glob("*.mcpb"))
        if len(candidates) != 1:
            raise ValueError(
                "The bundle directory must contain exactly one .mcpb file."
            )
        bundle = candidates[0]
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv before running the bundle smoke test.")
    with tempfile.TemporaryDirectory(prefix="flin bigquery smoke ") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(bundle) as archive:
            for entry in archive.infolist():
                if not (root / entry.filename).resolve().is_relative_to(root.resolve()):
                    raise ValueError("Bundle contains an unsafe archive path.")
            archive.extractall(root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        config = manifest["server"]["mcp_config"]
        substitutions = {
            "__dirname": str(root),
            "user_config.google_client_id": "smoke-client-id",
            "user_config.google_client_secret": "smoke-client-secret",
            "user_config.default_project": "smoke-project",
            "user_config.location": "EU",
            "user_config.max_bytes_billed": "1073741824",
        }

        def substitute(value: str) -> str:
            for name, replacement in substitutions.items():
                value = value.replace("${" + name + "}", replacement)
            if "${" in value:
                raise ValueError("Unresolved manifest variable.")
            return value

        environment = {key: substitute(value) for key, value in config["env"].items()}
        environment.update(
            {
                "GOOGLE_BIGQUERY_TOKEN_PATH": str(root / "test-tokens" / "token.json"),
                "GOOGLE_BIGQUERY_TOKEN_DIR": str(root / "test-tokens"),
            }
        )
        for key in ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR"):
            if key in os.environ:
                environment[key] = os.environ[key]
        parameters = StdioServerParameters(
            command=uv,
            args=[substitute(value) for value in config["args"]],
            env=environment,
        )
        assert {tool["name"] for tool in manifest["tools"]} == EXPECTED_TOOLS
        await verify_server(parameters)
        assert not (root / "test-tokens").exists(), (
            "Smoke test must never start OAuth or write tokens."
        )
        print(
            f"Bundle {manifest['version']}: 10 tools, configuration, annotations and validation verified."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    asyncio.run(check_bundle(parser.parse_args().bundle.resolve()))


if __name__ == "__main__":
    main()
