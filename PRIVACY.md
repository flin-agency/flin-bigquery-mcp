# Privacy

This local server sends selected project, dataset, table and query requests to Google BigQuery. Results are returned to the MCP client, whose own data handling policy applies. No flin-hosted service, analytics or telemetry is used by this package.

OAuth credentials are stored on the user's computer and refreshed through Google. ADC uses the credential source configured in the environment. The local OAuth token files contain sensitive refresh tokens and must not be shared or committed. To disconnect an OAuth account, stop the server, remove its local token file and revoke the application's Google account authorization if needed.

Query SQL and job metadata can be retained in Google Cloud job history and audit logs under the project's policies. Source data and table descriptions are returned only when requested by a tool. Remote functions or federated queries may involve additional services configured in Google Cloud.

See [Google's privacy policy](https://policies.google.com/privacy).
