# Security review: 0.1.2

Reviewed 2026-11-06. Scope: runtime source, OAuth/ADC, token storage, SQL execution and billing guards, MCP tools and error handling, desktop launcher, build scripts, dependency lock, Git history and release workflows. This is a source review with automated checks, not an independent penetration test.

## Findings and corrections

| Finding | Assessment | Correction |
| --- | --- | --- |
| Locked `oauthlib` 4.0.0 has CVE-2026-49272 / GHSA-3jp2-3mrg-2vxc | Upstream high-severity advisory concerns a device-code token endpoint. This application uses Google's installed-app authorization-code client and does not expose that endpoint. No reachable exploit identified in this application. | Upgrade to 4.0.1 and require `oauthlib>=4.0.1,<5` in distributed package metadata. |
| Token writes checked storage security, but reads followed links and accepted permissive files | Local credential disclosure or account substitution risk when storage is misconfigured. | Reads validate the parent directory, reject symlinks/non-regular files/hard links, check file identity across open, enforce POSIX ownership and private permissions, and bound/validate JSON input. Invalid storage does not trigger OAuth automatically. |
| OAuth PKCE depended on dependency defaults | Defence in depth; the installed library already enabled PKCE. | Explicitly enable PKCE and test the actual authorization URL for an S256 challenge. |
| GitHub Actions referenced movable version tags | Build supply-chain hardening opportunity. | Pin actions to verified commit IDs, disable persisted checkout credentials and add Dependabot configuration. |
| Installer smoke test used the previous published server before release | New server regressions could be missed by the packaging test. | Test the exact candidate wheel through the bundle launcher before publication; afterwards test the unchanged installer against PyPI and verify the reported server version. New bundles require server 0.1.2 or newer. |
| No dependency advisory gate in release builds | Known vulnerable dependencies could be released unnoticed. | Add pip-audit checks to CI and release builds. |

The upstream advisory and patch information are available at [oauthlib's security advisory](https://github.com/oauthlib/oauthlib/security/advisories/GHSA-3jp2-3mrg-2vxc). The explicit PKCE setting follows [Google's installed-app OAuth guidance](https://developers.google.com/identity/protocols/oauth2/native-app).

## Verification

- 104 tests pass locally on macOS with Python 3.12, including a real stdio MCP handshake, SDK request-boundary tests, SQL rejection, byte limits, parameterization, pagination, sanitized errors, token permissions/link/race/content tests and cached-launcher updates.
- Ruff lint and formatting checks pass.
- pip-audit 2.10.1 reports no known vulnerabilities in the updated locked runtime dependencies for the local Python 3.12 environment. CI repeats the audit for its Python/OS matrix.
- Bandit 1.9.4 reports no medium/high findings. All five low-priority detections are false positives: the fixed Google token endpoint and boolean `has_token_file` values, not embedded passwords.
- Gitleaks 8.30.1 found no secrets in the five existing Git commits before this release. Its binary checksum was verified against the upstream release. Test credential strings are synthetic.
- Bundle creation validates the MCPB schema, enforces an explicit file allowlist, rejects symlinked inputs and tests deterministic archive output. The runtime smoke test uses placeholder configuration and no Google credentials.

## Limits and residual risks

No live Google sign-in, private-data access, or billable query was performed. Claude Desktop's graphical installation flow was not exercised; the actual manifest launch command and MCP handshake are tested. The package is unsigned. IAM, local OS account security, future PyPI/dependency releases, downstream SELECT routines, and cumulative query costs remain trust boundaries; see [SECURITY.md](../SECURITY.md). No claim is made that automated scans prove the absence of vulnerabilities.
