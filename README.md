# flin-bigquery-mcp

MCP server for exploring Google BigQuery and running bounded, read-only GoogleSQL queries. Follows the Python/FastMCP, desktop OAuth, multi-account token storage and `uv` packaging conventions of [flin Search Console MCP](https://github.com/flin-agency/flin-google-search-console-mcp) and [flin Keyword Planner MCP](https://github.com/flin-agency/flin-google-keyword-planner-mcp).

## Mac installation (Claude Desktop)

Download `flin-bigquery-mcp-0.1.0-macos.mcpb` from the [GitHub release](https://github.com/flin-agency/flin-bigquery-mcp/releases/latest) and open it with Claude Desktop. You can also use Claude Desktop's local extension installation dialog and select the file.

The installer asks for your Google Desktop OAuth client ID and secret, default billing project, optional BigQuery location, and maximum bytes billed per query (default 1 GiB). Configure Google Cloud as described below before the first data request. Google sign-in opens in the browser when needed.

The extension contains the server source and a dependency lock file. It uses the MCPB `uv` runtime with Python 3.12, supports Apple Silicon and Intel Macs, and needs internet access on first launch to install Python/dependencies. A current Claude Desktop version with `uv` extension support is required. The `.mcpb` is an unsigned local extension, not a notarized macOS application; it does not require administrator access or a separate repository checkout. For other MCP clients, use the PyPI or source configuration below.

## Quickstart

1. Enable the **BigQuery API** in your Google Cloud project and configure billing for query jobs.
2. Grant the Google account **BigQuery Job User** (`roles/bigquery.jobUser`) on the job/billing project and **BigQuery Data Viewer** (`roles/bigquery.dataViewer`) on the datasets to read. Metadata discovery also depends on the account's project/dataset permissions. Avoid using an admin identity.
3. Configure the OAuth consent screen. For an external app in testing, add your Google account as a test user.
4. Create an OAuth client of type **Desktop app**. Use its client ID and secret below. The local loopback callback is managed by the server.
5. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and clone this repository. Add this entry to your MCP client's configuration:

```json
{
  "mcpServers": {
    "flin-bigquery-mcp": {
      "command": "uv",
      "args": [
        "run", "--directory", "/absolute/path/to/flin-bigquery-mcp",
        "--locked", "flin-bigquery-mcp"
      ],
      "env": {
        "GOOGLE_CLIENT_ID": "your-desktop-client-id",
        "GOOGLE_CLIENT_SECRET": "your-desktop-client-secret",
        "GOOGLE_BIGQUERY_PROJECT": "your-billing-project",
        "GOOGLE_BIGQUERY_LOCATION": "EU"
      }
    }
  }
}
```

Replace the path and values, then restart the client. `health_check` checks configuration locally. `list_projects` or the first data call opens Google sign-in when needed. Tokens are saved locally and refreshed automatically. OAuth waits for up to three minutes; retry the tool if sign-in expires.

This is a local **stdio** server, usable with clients such as Claude Desktop and Codex that support local MCP processes. No HTTP endpoint or cloud deployment is provisioned.

The published package can be used with `"command": "uvx", "args": ["flin-bigquery-mcp@latest"]`.

## Tools

| Tool | Purpose |
| --- | --- |
| `health_check` | Local settings and saved-token status; does not verify Google access |
| `list_projects` | One page of accessible projects |
| `list_datasets` | One page of datasets in a project |
| `get_dataset` | Dataset location, description and labels |
| `list_tables` | One page of tables and views |
| `get_table` | Nested schema, row count, size, partitioning and clustering |
| `preview_table` | Bounded rows from a physical table without running a SQL query |
| `dry_run_query` | Validate a single SELECT and estimate scanned bytes |
| `run_query` | Validate and submit a bounded SELECT; returns a job reference |
| `get_query_results` | Poll a query job and page through its results |

All data tools support `account`. Project-specific tools use `project_id`, falling back to `GOOGLE_BIGQUERY_PROJECT`. Pass dataset and table IDs separately, without project prefixes. `list_projects` works without a default project. Query `project_id` determines where the job is created and billed; fully qualified SQL can read another accessible project.

### Example workflow

1. `health_check`, then `list_projects`.
2. `list_datasets`, `get_dataset` (check its location), `list_tables`, `get_table`.
3. `preview_table` to inspect a few rows, or `dry_run_query` to estimate a query.
4. `run_query` once, then `get_query_results` with the returned `job_id`, `project_id`, `location` and the same account.
5. If `job_complete` is false, poll again later. For subsequent pages, pass `next_page_token` unchanged. Do not call `run_query` again to poll.

A parameterized query:

```json
{
  "sql": "SELECT event_name, COUNT(*) AS events FROM `data-project.analytics.events_*` WHERE _TABLE_SUFFIX BETWEEN @start_date AND @end_date GROUP BY event_name ORDER BY events DESC LIMIT 20",
  "project_id": "billing-project",
  "location": "EU",
  "parameters": [
    {"name": "start_date", "type": "STRING", "value": "20261001"},
    {"name": "end_date", "type": "STRING", "value": "20261007"}
  ],
  "maximum_bytes_billed": 1073741824
}
```

Named scalar parameters are supported; ARRAY/STRUCT parameters are not yet exposed. Result pages contain at most 1,000 rows (default 100); previews default to 20. A page token is tied to its resource/job and account. Results expire according to BigQuery's anonymous result-table retention. Dates/times use ISO strings, NUMERIC/BIGNUMERIC use decimal strings, BYTES use base64, and non-finite floats use strings. Arrays and nested records are preserved. Large STRING/BYTES cells can still produce large responses despite the row limit.

## Query controls and permissions

- Every execution is preceded by a Google BigQuery dry run. Google's parsed `statement_type` must be `SELECT`. Scripts, stored procedure calls, DDL, DML, exports and unknown statement types are rejected before execution.
- Default hard ceiling: **1 GiB (1,073,741,824 bytes) per query**. Set `GOOGLE_BIGQUERY_MAX_BYTES_BILLED` to change it. Tool arguments may lower but cannot raise this ceiling.
- Both the dry-run estimate and the submitted job are checked/bounded. Estimates may be incomplete for external or federated sources. `maximum_bytes_billed` limits BigQuery on-demand bytes, not every possible external, remote-function, ML or reservation charge.
- A SQL `LIMIT` limits output rows, not scanned bytes. Filter partitions and select only needed columns.
- `run_query` is marked non-idempotent and not read-only in MCP annotations because it creates a potentially billable job. Its allowed SQL only reads data. Polling results does not submit new queries.
- The Google client uses `jobs.insert`, which requires the **`https://www.googleapis.com/auth/bigquery`** scope. That scope is broader than the server's tool surface. IAM permissions are the underlying access boundary; the server deliberately exposes no write operations or user-supplied destination/job configuration.
- SELECT queries can invoke existing views, routines or remote functions allowed by IAM. SQL classification does not sandbox their downstream effects. Use a dedicated identity with only the intended dataset/job permissions.
- Query submission uses a generated job ID and disables automatic job re-execution. If a transport error occurs after submission, check BigQuery job history before manually retrying to avoid duplicate charges.

## Authentication and settings

| Variable | Default / use |
| --- | --- |
| `GOOGLE_BIGQUERY_AUTH_MODE` | `oauth`; alternatively `adc` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Required in OAuth mode |
| `GOOGLE_BIGQUERY_PROJECT` | Default metadata and billing/job project; otherwise pass `project_id` |
| `GOOGLE_BIGQUERY_LOCATION` | Optional location (`EU`, `US`, or a region); must match the queried data |
| `GOOGLE_BIGQUERY_MAX_BYTES_BILLED` | `1073741824`; positive integer |
| `GOOGLE_BIGQUERY_TOKEN_PATH` | Default account's token file |
| `GOOGLE_BIGQUERY_TOKEN_DIR` | Named account token directory; defaults to the default token's directory |
| `GOOGLE_BIGQUERY_OAUTH_PORT` | `0` (available local loopback port) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Standard Google ADC credential file setting |

Default OAuth token paths:

- macOS: `~/Library/Application Support/flin-bigquery-mcp/token.json`
- Linux: `~/.config/flin-bigquery-mcp/token.json`
- Windows: `%APPDATA%\flin-bigquery-mcp\token.json`

Use `account: "work"` to keep another account in `work.json`. Account names allow letters, digits, `_`, `-`, `.` and cannot alias the default token file. Tokens are written atomically, with private file permissions on POSIX. Use a private directory owned by your user. Named accounts refer to separate sign-ins, not Google account IDs.

For service accounts, workload identity, or existing `gcloud auth application-default login` credentials:

```json
{
  "GOOGLE_BIGQUERY_AUTH_MODE": "adc",
  "GOOGLE_BIGQUERY_PROJECT": "your-billing-project",
  "GOOGLE_BIGQUERY_LOCATION": "EU"
}
```

Optionally set `GOOGLE_APPLICATION_CREDENTIALS` to a credential file outside the repository. ADC mode does not support named `account` values. `health_check` always returns `adc_not_checked` with `ok: false` in ADC mode; verify access through a data tool. It never contacts metadata servers or opens a browser to probe ADC. Grant the ADC identity the same minimal BigQuery roles.

## Development

```sh
uv sync --locked --extra dev
uv run pytest
uv run ruff check src tests scripts mcpb
uv run ruff format --check src tests scripts mcpb
uv build
uv run python scripts/build_mcpb.py
uv run python scripts/check_mcpb.py dist/mcpb
```

`.env.example` documents configuration. The server does not implicitly load `.env`; use client `env` settings or `uv run --env-file .env flin-bigquery-mcp` for local development. Never commit credentials or tokens.

Tests run without credentials and mock Google API calls. They cover OAuth refresh/storage, account isolation, query rejection, byte ceilings, pagination, serialization, sanitized errors, and a real stdio MCP handshake/tool call. See [testing](docs/testing.md) for the optional live check.

See [release instructions](docs/release.md), [privacy](PRIVACY.md), and [support](SUPPORT.md).

## Troubleshooting

- `missing_configuration` / `invalid_configuration`: check the selected authentication mode, required OAuth values, project, account name and positive byte ceiling.
- `authentication_required`: complete Google sign-in or configure ADC. External OAuth apps in testing may require renewed consent.
- `permission_denied`: check API enablement, job-user and data-viewer access, billing and quotas.
- `not_found`: check IDs and the returned job location. An EU job cannot be fetched as a US job.
- `query_rejected`: use a single SELECT (including CTEs), not a script or write operation.
- `cost_limit_exceeded`: reduce scanned columns/date partitions or deliberately change the configured server ceiling.
- `invalid_request`: check SQL, parameter types and region. Detailed SQL-bearing upstream errors are deliberately not returned to the model; inspect the Google Cloud console when needed.

## Official references

- [BigQuery access control](https://cloud.google.com/bigquery/docs/access-control)
- [Running queries and dry runs](https://cloud.google.com/bigquery/docs/running-queries)
- [Job insertion and OAuth scopes](https://cloud.google.com/bigquery/docs/reference/rest/v2/jobs/insert)
- [Query job configuration and maximum bytes billed](https://cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.QueryJobConfig)
- [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
