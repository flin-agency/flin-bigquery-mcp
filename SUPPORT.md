# Support

Report issues at [GitHub Issues](https://github.com/flin-agency/flin-bigquery-mcp/issues) or contact **flin@flin.agency**. Report security problems privately; see [SECURITY.md](SECURITY.md).

Include the installed **extension version**, `connection_status.server_version` (or `health_check.server_version`), Mac architecture, OS, Claude Desktop version and sanitized error code. Never include OAuth secrets, tokens, keys, customer data or sensitive SQL. Obtain required setup values from your administrator/password manager.

- Incomplete setup: check the Desktop OAuth client ID/secret and positive byte limit.
- `auth_status: unknown`: a local token/ADC setting is not a live access check. Use `list_datasets` for the intended project; this creates no SQL query job. Use `list_projects` to initiate Google sign-in when needed.
- Permission error: verify Data Viewer on the intended datasets and Job User on the billing project. Dataset/data projects can differ from the billing project.
- Startup/update failure: restore connectivity to PyPI and restart Claude Desktop. Cached code is not silently used. For a prolonged registry outage, an administrator can use the [prepared-checkout fallback](README.md#prepared-checkout-fallback). Keep existing settings and tokens.
- Wrong version shown: Claude's extension version is the launcher version; check the running server version separately. A running session needs a restart for updates.

To revoke access and clean up local credentials, follow [PRIVACY.md](PRIVACY.md).
