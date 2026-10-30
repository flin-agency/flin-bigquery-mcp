# Testing

Run `uv sync --locked --extra dev`, then `uv run pytest`. Tests never require Google credentials or execute billable queries. The stdio test launches the actual server, initializes an MCP session, discovers tools, checks annotations, calls health_check and verifies input validation.

Optional live validation after configuring a dedicated test identity:

1. Run `health_check`, then `list_projects` and sign in.
2. List a known project's datasets and inspect one dataset/table.
3. Preview one physical table with `page_size: 1`; continue using its token.
4. Dry-run `SELECT @value AS value` with an INT64 parameter of 1.
5. Submit the same query once with `run_query`; retrieve its result using the returned job ID and location.
6. Query `SELECT x FROM UNNEST([1,2,3]) AS x ORDER BY x`; retrieve three pages with `page_size: 1`, checking no rows repeat.
7. Request `maximum_bytes_billed` above the configured ceiling; it must be rejected before any API query is sent.

Do not run write statements against production to test rejection. Automated tests cover Google's non-SELECT classifications with mocked responses. Live testing is separate from the offline suite and may incur Google charges.
