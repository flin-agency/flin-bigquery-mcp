"""Exercise the real Google SDK against a fake HTTP boundary (no Google calls)."""

from unittest.mock import Mock

from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

from flin_bigquery_mcp.bigquery import BigQueryService
from flin_bigquery_mcp.config import load_settings


def test_real_sdk_submits_dry_run_then_bounded_job_and_paginates():
    settings = load_settings(
        {
            "GOOGLE_BIGQUERY_AUTH_MODE": "adc",
            "GOOGLE_BIGQUERY_PROJECT": "billing-project",
        }
    )
    client = bigquery.Client(
        project="billing-project", credentials=AnonymousCredentials()
    )
    service = BigQueryService(client, settings)
    requests = []

    def respond(**kwargs):
        requests.append(kwargs)
        path = kwargs["path"]
        if kwargs["method"] == "POST":
            body = kwargs["data"]
            return {
                **body,
                "statistics": {
                    "query": {"statementType": "SELECT", "totalBytesProcessed": "100"}
                },
                "status": {
                    "state": "DONE"
                    if body["configuration"].get("dryRun")
                    else "RUNNING"
                },
            }
        if "/jobs/" in path:
            return {
                "jobReference": {
                    "projectId": "billing-project",
                    "jobId": "one",
                    "location": "EU",
                },
                "configuration": {
                    "query": {
                        "query": "SELECT 1",
                        "destinationTable": {
                            "projectId": "billing-project",
                            "datasetId": "anon",
                            "tableId": "results",
                        },
                    }
                },
                "status": {"state": "DONE"},
                "statistics": {"query": {"statementType": "SELECT"}},
            }
        if path.endswith("/data"):
            second = kwargs["query_params"].get("pageToken") == "opaque"
            return {
                "totalRows": "2",
                "rows": [{"f": [{"v": "2" if second else "1"}]}],
                **({} if second else {"pageToken": "opaque"}),
            }
        if path.endswith("/tables/results"):
            return {
                "tableReference": {
                    "projectId": "billing-project",
                    "datasetId": "anon",
                    "tableId": "results",
                },
                "schema": {"fields": [{"name": "value", "type": "INTEGER"}]},
                "numRows": "2",
            }
        raise AssertionError(path)

    client._connection.api_request = Mock(side_effect=respond)
    submitted = service.run_query("SELECT 1", None, "EU", None, 1000)
    assert submitted["state"] == "RUNNING"
    assert requests[0]["data"]["configuration"]["dryRun"] is True
    assert requests[1]["data"]["configuration"]["dryRun"] is False
    assert requests[1]["data"]["configuration"]["query"]["maximumBytesBilled"] == "1000"
    first = service.get_query_results("one", None, "EU", 1, None)
    second = service.get_query_results("one", None, "EU", 1, first["next_page_token"])
    assert first["rows"] == [{"value": 1}]
    assert second["rows"] == [{"value": 2}]
    assert second["next_page_token"] is None
    assert len([r for r in requests if r["method"] == "POST"]) == 2
    assert all(
        r["query_params"]["maxResults"] == 1
        for r in requests
        if r["path"].endswith("/data")
    )
    client.close()
