## Installation on macOS

Download **flin-bigquery-mcp-0.1.2-macos.mcpb** below and open it with Claude Desktop, or select it in Claude Desktop's local extension installation dialog. Requires a current Claude Desktop with `uv` extension support. Supports Apple Silicon and Intel Macs. Configure your Google Desktop OAuth client and BigQuery permissions as described in the [README](https://github.com/flin-agency/flin-bigquery-mcp#mac-installation-claude-desktop).

## Security changes

- Upgrade oauthlib to a patched version and enforce a minimum version in the published package.
- Reject unsafe token files on read, including links, incorrect POSIX permissions and oversized/malformed content.
- Explicitly enable OAuth PKCE.
- Pin GitHub Actions, add dependency auditing, and test the exact candidate package before publication.
- Require server 0.1.2 or newer in the Mac launcher.

See the [security review](https://github.com/flin-agency/flin-bigquery-mcp/blob/v0.1.2/docs/security-review-0.1.2.md) for checks and limits.

Existing correctly stored tokens continue to work. Manually copied tokens may need owner-only permissions (`0600`) on macOS/Linux. If a token was exposed, revoke it and sign in again.

The launcher continues checking PyPI for stable updates on each server start. The `.mcpb` is an unsigned local extension; `SHA256SUMS` covers the attached installer, wheel and source archive. No live Google sign-in or billable query was performed during verification.
