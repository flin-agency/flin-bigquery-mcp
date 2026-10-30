"""Verify package and lock versions, plus the GitHub release tag when present."""

import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from flin_bigquery_mcp import __version__

ROOT = Path(__file__).resolve().parents[1]
project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
lock = tomllib.loads((ROOT / "uv.lock").read_text())
locked = next(p["version"] for p in lock["package"] if p["name"] == project["name"])
if project["version"] != __version__ or locked != __version__:
    raise SystemExit("Package, project and lock versions must match.")
if (
    os.environ.get("GITHUB_REF_TYPE") == "tag"
    and os.environ.get("GITHUB_REF_NAME") != f"v{__version__}"
):
    raise SystemExit("Release tag does not match package version.")
print(f"Version {__version__} verified.")
