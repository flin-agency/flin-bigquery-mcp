# Privacy

This local stdio server sends requested project/dataset/table metadata, SQL and query parameters to Google BigQuery. Returned data goes to the MCP client (for example Claude Desktop), whose own data handling policy applies. SQL/job metadata may remain in Google Cloud job history and audit logs. Remote functions or federated queries may contact additional services configured in Google Cloud. The package operates no flin-hosted backend, telemetry or analytics.

Google OAuth sign-in runs in the browser with a local loopback callback. The Desktop client values come from your administrator/password manager. OAuth refresh/access tokens are saved as **JSON files**, not encrypted by this package and not placed in Keychain by it. On macOS the default is `~/Library/Application Support/flin-bigquery-mcp/token.json`; named accounts use `<account>.json` in that directory. File permissions are private on POSIX. Custom token paths and ADC credential sources are described in the [README](README.md#authentication-and-settings).

At startup the desktop launcher checks PyPI and downloads compatible server/dependency packages. The `uv` runtime may also download Python from its runtime distribution hosts. The package does not send BigQuery data or Google tokens to PyPI. `connection_status` and `health_check` make no network requests.

To disconnect: quit the MCP client, revoke the application's access in your Google Account's third-party connections, and delete the selected token JSON file (including named-account files you no longer need). Remove stored OAuth settings or uninstall the extension in Claude Desktop. For ADC, remove/revoke the configured credential source using your organization's Google Cloud procedure; deleting this extension's OAuth token does not revoke ADC. Uninstalling the extension alone does not guarantee token-file deletion. Never share token files or credentials in support tickets.

See [Google's privacy policy](https://policies.google.com/privacy) and the [security policy](SECURITY.md).
