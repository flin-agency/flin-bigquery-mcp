# /// script
# requires-python = ">=3.12"
# dependencies = ["flin-bigquery-mcp>=0.1.3,<0.2"]
# ///
"""Load the PyPI server; uv refreshes this dependency on every extension start."""

from flin_bigquery_mcp.server import main

if __name__ == "__main__":
    main()
