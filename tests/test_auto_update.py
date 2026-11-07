"""Run the same installer twice with a warm uv cache and a newly published wheel."""

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def package_index(directory, kind):
    if kind == "directory":
        yield ["--no-index", "--find-links", str(directory)], None
        return

    state = {"requests": 0, "available": True}

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/simple/flin-bigquery-mcp/":
                state["requests"] += 1
                if not state["available"]:
                    self.send_error(503)
                    return
                # Like PyPI's simple index, advertise wheels over HTTP. A long
                # cache lifetime reproduces stale metadata unless uv refreshes it.
                links = "\n".join(
                    f'<a href="/wheels/{wheel.name}">{wheel.name}</a>'
                    for wheel in sorted(directory.glob("*.whl"))
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(links)))
                self.end_headers()
                self.wfile.write(links)
                return
            self.path = self.path.removeprefix("/wheels")
            super().do_GET()

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(directory))
    ) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield (
                ["--default-index", f"http://127.0.0.1:{server.server_port}/simple"],
                state,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)


def make_wheel(directory, version):
    info = f"flin_bigquery_mcp-{version}.dist-info"
    contents = {
        "flin_bigquery_mcp/__init__.py": "",
        "flin_bigquery_mcp/server.py": f'''import os
from pathlib import Path

def main():
    assert os.environ["GOOGLE_BIGQUERY_PROJECT"] == "saved-project"
    assert os.environ["GOOGLE_BIGQUERY_MAX_BYTES_BILLED"] == "1073741824"
    assert Path(os.environ["GOOGLE_BIGQUERY_TOKEN_PATH"]).read_text() == "synthetic-saved-token"
    print("{version}")
''',
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
@pytest.mark.parametrize("index_kind", ["directory", "http"])
def test_next_start_updates_cached_server_without_reinstalling_bundle(
    tmp_path, index_kind
):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for the installer integration test")
    launcher = tmp_path / "installed extension" / "server.py"
    launcher.parent.mkdir()
    shutil.copyfile(ROOT / "mcpb" / "server.py", launcher)
    original = launcher.read_bytes()
    wheels = tmp_path / "package-index"
    wheels.mkdir()
    make_wheel(wheels, "0.1.3")
    manifest = json.loads((ROOT / "mcpb" / "manifest.template.json").read_text())
    args = [
        arg.replace("${__dirname}", str(launcher.parent))
        for arg in manifest["server"]["mcp_config"]["args"]
    ]
    # Use a local wheel index instead of PyPI, and the CI test interpreter.
    args[args.index("--python") + 1] = sys.executable
    index_position = args.index("--default-index")
    del args[index_position : index_position + 2]
    environment = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("UV_", "GOOGLE_", "PYTHON")) and k != "VIRTUAL_ENV"
    }
    environment.update(
        UV_CACHE_DIR=str(tmp_path / "warm-cache"),
        UV_PYTHON_DOWNLOADS="never",
        UV_HTTP_RETRIES="0",
        UV_HTTP_TIMEOUT="3",
    )

    token = tmp_path / "saved-token.json"
    token.write_text("synthetic-saved-token")
    environment.update(
        GOOGLE_BIGQUERY_PROJECT="saved-project",
        GOOGLE_BIGQUERY_MAX_BYTES_BILLED="1073741824",
        GOOGLE_BIGQUERY_TOKEN_PATH=str(token),
    )

    def start(*, check=True):
        return subprocess.run(
            [uv, *args],
            env=environment,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=check,
            timeout=60,
        )

    with package_index(wheels, index_kind) as (index_args, state):
        args[-1:-1] = index_args
        assert start().stdout.strip() == "0.1.3"
        requests_before_update = state["requests"] if state else None
        make_wheel(wheels, "0.1.4")
        make_wheel(wheels, "0.1.5rc1")
        assert start().stdout.strip() == "0.1.4"
        if state:
            assert state["requests"] > requests_before_update
        make_wheel(wheels, "0.2.0")
        make_wheel(wheels, "1.0.0")
        assert start().stdout.strip() == "0.1.4"
        make_wheel(wheels, "0.1.5")
        assert start().stdout.strip() == "0.1.5"
        assert launcher.read_bytes() == original
        assert token.read_text() == "synthetic-saved-token"
        if state:
            state["available"] = False
            failed = start(check=False)
            assert failed.returncode != 0
            assert not failed.stdout.strip(), "Do not silently run a cached old version"
