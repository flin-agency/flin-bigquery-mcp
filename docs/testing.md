# Testing

Run `uv sync --locked --extra dev`, then `uv run pytest`. Tests never require Google credentials or execute billable queries. The stdio test launches the actual server, initializes an MCP session, discovers tools, checks annotations, calls connection_status and health_check and verifies input validation.

Optional live validation after configuring a dedicated test identity:

1. Run `connection_status` (local only), then `list_projects` and sign in. Use `list_datasets` on the intended project for a metadata-only live test without a query job.
2. List a known project's datasets and inspect one dataset/table.
3. Preview one physical table with `page_size: 1`; continue using its token.
4. Dry-run `SELECT @value AS value` with an INT64 parameter of 1.
5. Submit the same query once with `run_query`; retrieve its result using the returned job ID and location.
6. Query `SELECT x FROM UNNEST([1,2,3]) AS x ORDER BY x`; retrieve three pages with `page_size: 1`, checking no rows repeat.
7. Request `maximum_bytes_billed` above the configured ceiling; it must be rejected before any API query is sent.

Do not run write statements against production to test rejection. Automated tests cover Google's non-SELECT classifications with mocked responses. Live testing is separate from the offline suite and may incur Google charges.

Bundle smoke tests run the manifest command from a temporary directory outside the source checkout. Release builds check the native Apple Silicon architecture; CI also retains Intel Mac, Linux and Windows. The cached HTTP-index regression covers the stable 0.1.x range, prerelease rejection, blocked future 0.2/1.0 versions, unchanged saved settings/token fixture and explicit failure during index outages. These are synthetic tests, not a graphical Claude Desktop install or a real customer-account test.
