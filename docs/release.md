# Release

The project follows the flin GitHub Actions / PyPI Trusted Publisher release model. No release is published merely by pushing source to main.

1. Configure a PyPI Trusted Publisher: owner `flin-agency`, repository `flin-bigquery-mcp`, workflow `release.yml`, environment `pypi`.
2. Update the version in `pyproject.toml` and `src/flin_bigquery_mcp/__init__.py`; run `uv lock`.
3. Run tests, lint, formatting and `uv build --out-dir dist/python`. Run `uv run python scripts/build_mcpb.py`, and `uv run python scripts/check_mcpb.py dist/mcpb --server-wheel dist/python`. Verify the generated wheel and source distribution contain the runtime and no credentials.
4. Commit and push the tested sources, then create and push the matching `vX.Y.Z` tag when publication is intended.
5. The workflow verifies the tag, runs checks, smoke-tests the Mac extension on macOS, builds distributions and publishes through PyPI's trusted publisher. Confirm package installation from PyPI before recommending `uvx flin-bigquery-mcp@latest`.

Manual workflow dispatch builds artifacts only; publication requires a version tag. Configure GitHub's `pypi` environment protection as appropriate for the organization.

After PyPI publication succeeds, the workflow creates a GitHub release with the Python distributions, the macOS `.mcpb` extension and `SHA256SUMS`. The extension is staged from an explicit runtime allowlist; development files, credentials and local environments are excluded.

The desktop bundle from 0.1.1 onward is an updating launcher. From 0.1.2, pre-publication bundle tests override the server dependency with the exact candidate wheel and check its reported version. The installer requires server 0.1.2 or newer. After publishing, verify the unchanged bundle with `scripts/check_mcpb.py --expected-server-version X.Y.Z` before attaching it to the GitHub release. Future server-only PyPI releases are picked up on the next extension start. Launcher metadata and configuration changes still require reinstalling the new bundle.

Dependency audits run before publication. Actions are pinned to full commit IDs and checkout does not persist credentials. Dependabot proposes dependency and action updates. Review the version-specific release notes before tagging; the release workflow attaches SHA-256 checksums for every distribution.
