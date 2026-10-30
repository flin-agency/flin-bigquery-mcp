# Release

The project follows the flin GitHub Actions / PyPI Trusted Publisher release model. No release is published merely by pushing source to main.

1. Configure a PyPI Trusted Publisher: owner `flin-agency`, repository `flin-bigquery-mcp`, workflow `release.yml`, environment `pypi`.
2. Update the version in `pyproject.toml` and `src/flin_bigquery_mcp/__init__.py`; run `uv lock`.
3. Run tests, lint, formatting and `uv build`. Verify the generated wheel and source distribution contain the runtime and no credentials.
4. Commit and push the tested sources, then create and push the matching `vX.Y.Z` tag when publication is intended.
5. The workflow verifies the tag, runs checks, builds distributions and publishes through PyPI's trusted publisher. Confirm package installation from PyPI before recommending `uvx flin-bigquery-mcp@latest`.

Manual workflow dispatch builds artifacts only; publication requires a version tag. Configure GitHub's `pypi` environment protection as appropriate for the organization.
