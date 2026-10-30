from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.cloud import bigquery

from flin_bigquery_mcp.bigquery import (
    BigQueryService,
    CostLimitError,
    QueryParameter,
    QueryRejectedError,
    json_value,
)
from flin_bigquery_mcp.config import load_settings


@pytest.fixture
def service():
    settings = load_settings(
        {
            "GOOGLE_BIGQUERY_AUTH_MODE": "adc",
            "GOOGLE_BIGQUERY_PROJECT": "billing-project",
            "GOOGLE_BIGQUERY_LOCATION": "EU",
        }
    )
    return BigQueryService(MagicMock(), settings)


def job(statement="SELECT", size=100):
    return SimpleNamespace(
        statement_type=statement, total_bytes_processed=size, location="EU", schema=[]
    )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT",
        "DELETE",
        "UPDATE",
        "MERGE",
        "CREATE_TABLE",
        "DROP_TABLE",
        "EXPORT_DATA",
        "SCRIPT",
        "CALL",
        None,
    ],
)
def test_non_select_and_unknown_statements_never_execute(service, statement):
    service.client.query.return_value = job(statement)
    with pytest.raises(QueryRejectedError):
        service.run_query("anything", None, None, None, None)
    assert service.client.query.call_count == 1
    assert service.client.query.call_args.kwargs["job_config"].dry_run is True


def test_over_budget_query_never_executes(service):
    service.client.query.return_value = job(size=1073741825)
    with pytest.raises(CostLimitError):
        service.run_query("SELECT * FROM huge_table", None, None, None, None)
    assert service.client.query.call_count == 1


@pytest.mark.parametrize("limit", [0, -1, 1073741825])
def test_tool_cannot_raise_or_disable_server_ceiling(service, limit):
    with pytest.raises(CostLimitError):
        service.run_query("SELECT 1", None, None, None, limit)
    service.client.query.assert_not_called()


def test_query_keeps_identical_sql_parameters_location_and_budget(service):
    configs = []

    def query(sql, **kwargs):
        configs.append(kwargs["job_config"].to_api_repr())
        if len(configs) == 1:
            return job()
        return SimpleNamespace(
            job_id="job-123", project="billing-project", location="EU", state="PENDING"
        )

    service.client.query.side_effect = query
    parameter = QueryParameter(name="name", type="STRING", value="'; DROP TABLE x; --")
    sql = "WITH x AS (SELECT @name AS name) SELECT * FROM x"
    result = service.run_query(sql, None, None, [parameter], 500)
    assert result["job_id"] == "job-123"
    assert result["next_tool"] == "get_query_results"
    assert configs[0]["dryRun"] is True and configs[1]["dryRun"] is False
    assert (
        configs[0]["query"]["maximumBytesBilled"]
        == configs[1]["query"]["maximumBytesBilled"]
        == "500"
    )
    assert (
        configs[0]["query"]["queryParameters"] == configs[1]["query"]["queryParameters"]
    )
    for call in service.client.query.call_args_list:
        assert call.args[0] == sql
        assert call.kwargs["location"] == "EU"
        assert call.kwargs["project"] == "billing-project"
    assert service.client.query.call_args.kwargs["job_retry"] is None


def test_dry_run_does_not_submit_execution(service):
    service.client.query.return_value = job()
    result = service.dry_run_query("SELECT 1", "other-project", "US", None, None)
    assert result["estimated_bytes_processed"] == 100
    assert service.client.query.call_count == 1
    assert service.client.query.call_args.kwargs["job_config"].dry_run


def test_duplicate_parameters_rejected_before_api(service):
    param = QueryParameter(name="x", type="INT64", value=1)
    with pytest.raises(ValueError):
        service.run_query("SELECT @x", None, None, [param, param], None)
    service.client.query.assert_not_called()


def test_failed_dry_run_never_submits_real_job(service):
    service.client.query.side_effect = RuntimeError("failure")
    with pytest.raises(RuntimeError):
        service.run_query("SELECT 1", None, None, None, None)
    assert service.client.query.call_count == 1


def completed_job(service, *, state="DONE", error=None):
    value = bigquery.QueryJob("job-123", "SELECT 1", service.client)
    value._properties = {
        "jobReference": {
            "projectId": "billing-project",
            "jobId": "job-123",
            "location": "EU",
        },
        "configuration": {
            "query": {
                "query": "SELECT 1",
                "destinationTable": {
                    "projectId": "billing-project",
                    "datasetId": "anon",
                    "tableId": "result",
                },
            }
        },
        "status": {"state": state, **({"errorResult": error} if error else {})},
        "statistics": {
            "query": {
                "statementType": "SELECT",
                "totalBytesProcessed": "100",
                "cacheHit": False,
            }
        },
    }
    service.client.get_job.return_value = value
    return value


def iterator(items, token="next", schema=None):
    return SimpleNamespace(
        pages=iter([items]), next_page_token=token, schema=schema or [], total_rows=3
    )


def test_result_pages_use_same_endpoint_and_preserve_tokens(service):
    completed_job(service)
    service.client.list_rows.side_effect = [
        iterator([{"value": Decimal("0.123456789")}]),
        iterator([{"value": None}], None),
    ]
    first = service.get_query_results("job-123", None, "EU", 1, None)
    second = service.get_query_results(
        "job-123", None, "EU", 1, first["next_page_token"]
    )
    assert first["rows"] == [{"value": "0.123456789"}]
    assert second["next_page_token"] is None
    assert service.client.list_rows.call_args.kwargs == {
        "page_size": 1,
        "max_results": 1,
        "page_token": "next",
        "timeout": 30,
    }
    service.client.query.assert_not_called()


def test_pending_job_does_not_fetch_rows_or_resubmit(service):
    completed_job(service, state="RUNNING")
    result = service.get_query_results("job-123", None, None, 100, None)
    assert result["job_complete"] is False
    service.client.list_rows.assert_not_called()
    service.client.query.assert_not_called()


def test_job_errors_do_not_leak_sql_or_sensitive_messages(service):
    completed_job(service, error={"reason": "invalidQuery", "message": "secret SQL"})
    result = service.get_query_results("job-123", None, None, 100, None)
    assert result["ok"] is False
    assert "secret" not in str(result)
    service.client.list_rows.assert_not_called()


def test_discovery_keeps_pagination_bounded(service):
    service.client.list_projects.return_value = iterator(
        [SimpleNamespace(project_id="one", friendly_name="One")]
    )
    result = service.list_projects(1, "previous")
    assert result["next_page_token"] == "next"
    service.client.list_projects.assert_called_once_with(
        page_size=1, page_token="previous", timeout=30
    )


def test_preview_uses_tabledata_without_query(service):
    table = bigquery.Table(
        "billing-project.data.events", schema=[bigquery.SchemaField("x", "INTEGER")]
    )
    table._properties["type"] = "TABLE"
    service.client.get_table.return_value = table
    service.client.list_rows.return_value = iterator([{"x": 2}], None)
    result = service.preview_table("data", "events", None, 1, "opaque")
    assert result["rows"] == [{"x": 2}]
    assert service.client.list_rows.call_args.kwargs["max_results"] == 1
    service.client.query.assert_not_called()


def test_nested_values_are_json_serializable():
    import json

    row = bigquery.Row(
        (Decimal("123.000000001"), [b"abc", date(2026, 1, 1)], float("nan")),
        {"numeric": 0, "nested": 1, "special": 2},
    )
    result = json_value(row)
    assert result == {
        "numeric": "123.000000001",
        "nested": ["YWJj", "2026-01-01"],
        "special": "nan",
    }
    json.dumps(result, allow_nan=False)
