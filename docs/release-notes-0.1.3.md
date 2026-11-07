## Claude Desktop setup and status

- New `connection_status` reports the actual server version, local configuration/auth state, `live_access: not_checked`, and a concrete next step. No Google request, browser launch, token refresh or billable job occurs. Saved tokens and ADC are not represented as live-verified credentials. Existing tools and health fields remain available.
- The README starts with the Apple Silicon installation/sign-in/metadata-test flow, explains administrator-supplied values, dataset versus billing-project permissions, and the default 1 GiB per-query ceiling. Intel Mac and other-client setup remain supported.
- Both the versioned installer and the stable **flin-bigquery-mcp.mcpb** alias are attached with SHA-256 checksums. Privacy, security and support documentation explains token files, revocation, cleanup and startup recovery.

## Updates and compatibility

The new launcher accepts stable **`>=0.1.3,<0.2`** server versions on Python 3.12, preserving the entry point/configuration and discovering new tools from the server. It excludes prereleases and does not assume future minor/major lines are compatible. Automatic updates happen at server startup, preserving settings/tokens and leaving running sessions alone. Registry failure remains an explicit startup error; the README documents an administrator fallback.

Existing 0.1.1/0.1.2 installations can receive this server update through PyPI without reinstalling. **Import 0.1.3 once to apply the new compatibility bound to the installed launcher.** Claude's displayed extension version and the running server version may differ. No new required settings were introduced.

## Verification scope

The release workflow checks the candidate wheel through both the new installer and the recorded 0.1.2 installer on native Apple Silicon, then checks the published PyPI server through both launchers before publishing GitHub downloads. CI retains Intel Mac, Linux and Windows checks. Cached-index tests cover compatible upgrades, rejected prereleases/future version lines, preserved settings and token fixtures, and update failure behavior.

No real customer-account sign-in, graphical Claude Desktop installation or billable BigQuery query was performed. Metadata-only connection tests are documented; SELECT execution can still incur charges without changing source data.
