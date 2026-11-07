# Release and desktop update requirements

The user requires every published version to ship through both PyPI and GitHub's Claude Desktop downloads. Preserve these requirements when changing the project:

- Use the version-tag release workflow to publish the wheel and source distribution to PyPI and create a fresh versioned macOS `.mcpb` with checksums on GitHub. A source push alone is not a release.
- Existing Claude Desktop installations must obtain stable server updates from PyPI at the next MCP server start, without reinstalling the extension. Keep the launcher unpinned to an exact server version, within the tested 0.1.x compatibility line (`>=0.1.3,<0.2` for new bundles) and preserve the package refresh on every start. Do not introduce a frozen server copy into the bundle.
- Preserve compatibility with the installed 0.1.2 launcher: Python 3.12, its configuration variables, and its entry point. New mandatory installation fields or launcher changes must not silently become prerequisites for ordinary server updates. Provide backward-compatible defaults for new settings.
- Run the cached-update regression tests, the candidate-wheel smoke test through both the new bundle and the recorded installed bundle, and the post-publication PyPI checks. New tools must be discovered from the server without requiring an updated installed manifest.
- Do not report publication complete until PyPI serves the expected server version and GitHub provides the new installer. Report partial publication explicitly; never overwrite an existing PyPI version or retarget a published release tag to repair it.
- Explain that automatic updates occur at server startup. A running Claude Desktop session needs a restart; do not claim background hot-reloading or automatic replacement of Claude's installed manifest.
