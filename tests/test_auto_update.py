"""Run the same installer twice with a warm uv cache and a newly published wheel."""

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def make_wheel(directory, version):
    info = f"flin_bigquery_mcp-{version}.dist-info"
    contents = {
        "flin_bigquery_mcp/__init__.py": "",
        "flin_bigquery_mcp/server.py": f'def main():\n    print("{version}")\n',
        f"{info}/METADATA": f"Metadata-Version: 2.3\nName: flin-bigquery-mcp\nVersion: {version}\n",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    record = io.StringIO()
    writer = csv.writer(record)
    for name in [*contents, f"{info}/RECORD"]:
        writer.writerow([name, "", ""])
    contents[f"{info}/RECORD"] = record.getvalue()
    with zipfile.ZipFile(
        directory / f"flin_bigquery_mcp-{version}-py3-none-any.whl", "w"
    ) as archive:
        for name, value in contents.items():
            archive.writestr(name, value)


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="Desktop launcher requires Python 3.12"
)
def test_next_start_updates_cached_server_without_reinstalling_bundle(tmp_path):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for the installer integration test")
    launcher = tmp_path / "installed extension" / "server.py"
    launcher.parent.mkdir()
    shutil.copyfile(ROOT / "mcpb" / "server.py", launcher)
    original = launcher.read_bytes()
    wheels = tmp_path / "package-index"
    wheels.mkdir()
    make_wheel(wheels, "1.0.0")
    manifest = json.loads((ROOT / "mcpb" / "manifest.template.json").read_text())
    args = [
        arg.replace("${__dirname}", str(launcher.parent))
        for arg in manifest["server"]["mcp_config"]["args"]
    ]
    # Use a local wheel index instead of PyPI, and the CI test interpreter.
    args[args.index("--python") + 1] = sys.executable
    args[-1:-1] = ["--no-index", "--find-links", str(wheels)]
    environment = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("UV_", "GOOGLE_", "PYTHON")) and k != "VIRTUAL_ENV"
    }
    environment.update(
        UV_CACHE_DIR=str(tmp_path / "warm-cache"), UV_PYTHON_DOWNLOADS="never"
    )

    def start():
        return subprocess.run(
            [uv, *args],
            env=environment,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout.strip()

    assert start() == "1.0.0"
    make_wheel(wheels, "1.0.1")
    make_wheel(wheels, "2.0.0rc1")
    assert start() == "1.0.1"
    assert launcher.read_bytes() == original
