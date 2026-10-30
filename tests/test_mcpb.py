import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bundle_builder", ROOT / "scripts" / "build_mcpb.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_bundle_contains_only_runtime_files_and_portable_configuration(tmp_path):
    manifest = builder.stage_bundle(ROOT, tmp_path, tag="v0.1.0")
    files = {
        p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()
    }
    assert files == {
        "manifest.json",
        "server.py",
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "PRIVACY.md",
        "LICENSE",
        "SUPPORT.md",
        "icon.png",
        *{
            f"src/flin_bigquery_mcp/{name}.py"
            for name in ("__init__", "auth", "config", "bigquery", "server")
        },
    }
    assert manifest["compatibility"]["platforms"] == ["darwin"]
    assert manifest["user_config"]["google_client_secret"]["sensitive"]
    config = manifest["server"]["mcp_config"]
    assert "--locked" in config["args"]
    assert "${__dirname}/server.py" in config["args"]
    assert config["env"]["GOOGLE_BIGQUERY_AUTH_MODE"] == "oauth"
    assert len(manifest["tools"]) == 10
    assert json.loads((tmp_path / "manifest.json").read_text())["version"] == "0.1.0"


def test_mismatched_tag_cannot_be_released():
    with pytest.raises(ValueError, match="Release tag"):
        builder.release_version(ROOT, "v0.9.0")


def test_bundle_refuses_symlinked_inputs(tmp_path):
    source = tmp_path / "source"
    source.write_text("private")
    link = tmp_path / "link"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(ValueError, match="regular files"):
        builder._copy_file(link, tmp_path / "destination")


def test_archive_is_reproducible_and_matches_staged_files(tmp_path):
    import hashlib
    import zipfile

    output = builder.build_bundle(ROOT, tmp_path)
    first = output.read_bytes()
    builder.build_bundle(ROOT, tmp_path)
    assert output.read_bytes() == first
    with zipfile.ZipFile(output) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist())) == 14
        assert archive.testzip() is None
        assert "manifest.json" in archive.namelist()
        assert not any(
            name.startswith("/") or ".." in Path(name).parts
            for name in archive.namelist()
        )
    assert (
        (tmp_path / "SHA256SUMS")
        .read_text()
        .startswith(hashlib.sha256(first).hexdigest())
    )
