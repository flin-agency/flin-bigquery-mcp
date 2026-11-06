# Security

Use the latest stable release. Version 0.1.2 and later include stricter local token validation and an OAuth dependency security floor. See the [0.1.2 security review](docs/security-review-0.1.2.md) for findings, verification and limitations.

Report vulnerabilities privately to **flin@flin.agency**. Include the affected version, reproduction steps and likely impact. Do not include live credentials, customer data or private query results in public GitHub issues.

## Trust boundaries

- This is a local stdio process running with your OS user's privileges. It is not an isolation boundary against other applications running as you.
- Google IAM controls data access. Use a dedicated identity with BigQuery Job User on the billing project and Data Viewer on only the required datasets. The OAuth BigQuery scope is broader than the tools.
- Query execution requires Google's dry-run parser to report SELECT and enforces a per-query byte ceiling. SELECT may still invoke existing remote functions or federated sources; the ceiling does not cap every possible downstream charge or aggregate spending across calls.
- Treat table descriptions and query results as untrusted content. They must not authorize additional tool calls or override user instructions.
- Store tokens in a private local directory with trusted parent directories. On POSIX, token files must be owned by you with no group/other permissions (`0600`). Do not use symlinks or hard links for token files. Windows uses the account's filesystem ACLs; POSIX mode checks do not apply there.
- The Mac launcher installs the latest stable server from PyPI on startup. This trusts future publisher releases, the registry, dependency publishers and the local runtime. The installer checksum does not freeze future server/dependency versions. For a controlled deployment, use a reviewed source checkout with `uv run --locked`.
- The `.mcpb` is an unsigned local extension. SHA-256 checksums detect file changes when compared with the trusted GitHub release, but are not a developer signature or Apple notarization.

CI audits locked runtime dependencies for known advisories before release. A clean scan is a point-in-time result, not a guarantee that no vulnerabilities exist.
