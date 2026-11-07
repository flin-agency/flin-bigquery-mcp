# Release

The project follows the flin GitHub Actions / PyPI Trusted Publisher release model. No release is published merely by pushing source to main.

## Required release outcome

Every published version must produce both a PyPI release and a new macOS Claude Desktop installer on GitHub. These are one release workflow, not optional independent publishing paths. The new installer is provided for new installations; existing 0.1.2 installations must receive the server update from PyPI without reinstalling it.

The release is complete only after the published version starts through both the newly built installer and the unchanged installed 0.1.2 launcher. The workflow downloads the recorded 0.1.2 installer and validates its fixed SHA-256 before testing it with the candidate wheel, then tests the same installer against PyPI after publication. Its archive is kept separate from the new release assets. A failure blocks the GitHub release. If PyPI has already published, repair with a new version rather than overwriting it.

The cached-update integration test uses a local HTTP package index with a long cache lifetime. It verifies compatible 0.1.x stable upgrades, blocks 0.2/1.0 releases, skips prereleases, checks that the launcher remains unchanged, and confirms that an unavailable index does not silently start an outdated cached server.

Preserve Python 3.12 and the installed launcher's configuration contract. Add new settings with compatible defaults and expose new tools through MCP discovery. Changes to Claude's own extension form, launcher or runtime are outside PyPI server updates and need a separately planned extension migration; they must not be introduced as mandatory prerequisites for normal updates.

## Publication steps

1. Configure a PyPI Trusted Publisher: owner `flin-agency`, repository `flin-bigquery-mcp`, workflow `release.yml`, environment `pypi`.
2. Update the version in `pyproject.toml` and `src/flin_bigquery_mcp/__init__.py`; run `uv lock`.
3. Write `docs/release-notes-X.Y.Z.md`. Run tests, lint, formatting and `uv build --out-dir dist/python`. Run `uv run python scripts/build_mcpb.py`, and `uv run python scripts/check_mcpb.py dist/mcpb --server-wheel dist/python`. Verify the generated wheel and source distribution contain the runtime and no credentials.
4. Commit and push the tested sources, then create and push the matching `vX.Y.Z` tag when publication is intended.
5. The workflow verifies the tag, runs checks, smoke-tests the Mac extension on macOS, builds distributions and publishes through PyPI's trusted publisher. Confirm package installation from PyPI before recommending `uvx flin-bigquery-mcp@latest`.

Manual workflow dispatch builds artifacts only; publication requires a version tag. Configure GitHub's `pypi` environment protection as appropriate for the organization.

After PyPI publication succeeds, the workflow creates a GitHub release with the Python distributions, the macOS `.mcpb` extension and `SHA256SUMS`. The extension is staged from an explicit runtime allowlist; development files, credentials and local environments are excluded.

The desktop bundle from 0.1.1 onward is an updating launcher. From 0.1.2, pre-publication bundle tests override the server dependency with the exact candidate wheel and check its reported version. The 0.1.3 installer requires `>=0.1.3,<0.2`; the recorded 0.1.2 launcher remains a compatibility fixture with its original unbounded requirement. After publishing, verify the unchanged bundle with `scripts/check_mcpb.py --expected-server-version X.Y.Z` before attaching it to the GitHub release. Future server-only PyPI releases are picked up on the next extension start. Launcher metadata and configuration changes still require reinstalling the new bundle.

Dependency audits run before publication. Actions are pinned to full commit IDs and checkout does not persist credentials. Dependabot proposes dependency and action updates. Review the version-specific release notes before tagging; the release workflow attaches SHA-256 checksums for every distribution.

The stable alias `flin-bigquery-mcp.mcpb` must be byte-identical to the versioned installer and included in SHA256SUMS. The release build runs on Apple Silicon; Intel Mac, Linux and Windows checks remain separate in CI. No smoke test implies a real Google account or graphical Claude installation was tested.
