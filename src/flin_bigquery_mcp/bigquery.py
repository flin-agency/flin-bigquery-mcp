"""BigQuery operations; no table mutations or arbitrary job configurations are exposed."""

from __future__ import annotations

import base64
import math
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from google.cloud import bigquery
from pydantic import BaseModel, ConfigDict, Field

from .auth import get_credentials
from .config import ConfigurationError, Settings


class QueryParameter(BaseModel):
    """A named, scalar GoogleSQL parameter; values are never interpolated into SQL."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    type: Literal[
        "STRING",
        "INT64",
        "FLOAT64",
        "BOOL",
        "NUMERIC",
        "BIGNUMERIC",
        "DATE",
        "DATETIME",
        "TIME",
        "TIMESTAMP",
    ]
    value: str | int | float | bool | None


class QueryRejectedError(ValueError):
    pass


class CostLimitError(ValueError):
    pass


def create_client(settings: Settings, account: str | None = None) -> bigquery.Client:
    # projects.list doesn't require a billing project. All project-specific
    # operations resolve an explicit project before sending requests.
    return bigquery.Client(
        project=settings.default_project or "project-discovery",
        credentials=get_credentials(settings=settings, account=account),
        location=settings.location,
    )


def json_value(value: Any) -> Any:
    """Keep NUMERIC precision and make nested BigQuery values JSON-safe."""
    if isinstance(value, bigquery.Row):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def page_payload(iterator: Any, transform: Any) -> dict[str, Any]:
    page = next(iter(iterator.pages), None)
    items = [transform(item) for item in page] if page is not None else []
    return {"items": items, "next_page_token": iterator.next_page_token}


def schema_payload(schema: Any) -> list[dict[str, Any]]:
    return [field.to_api_repr() for field in schema]


class BigQueryService:
    def __init__(self, client: bigquery.Client, settings: Settings):
        self.client = client
        self.settings = settings

    def project(self, project_id: str | None) -> str:
        project = (project_id or self.settings.default_project or "").strip()
        if not project:
            raise ConfigurationError("Set GOOGLE_BIGQUERY_PROJECT or pass project_id.")
        return project

    def location(self, location: str | None) -> str | None:
        return location or self.settings.location

    def list_projects(self, page_size: int = 50, page_token: str | None = None) -> dict:
        return page_payload(
            self.client.list_projects(
                page_size=page_size, page_token=page_token, timeout=30
            ),
            lambda p: {"project_id": p.project_id, "friendly_name": p.friendly_name},
        )

    def list_datasets(
        self, project_id: str | None, page_size: int, page_token: str | None
    ) -> dict:
        project = self.project(project_id)
        result = page_payload(
            self.client.list_datasets(
                project=project, page_size=page_size, page_token=page_token, timeout=30
            ),
            lambda d: {
                "dataset_id": d.dataset_id,
                "project_id": d.project,
                "full_id": f"{d.project}.{d.dataset_id}",
            },
        )
        return {"project_id": project, **result}

    def dataset_ref(
        self, dataset_id: str, project_id: str | None
    ) -> bigquery.DatasetReference:
        if not dataset_id or "." in dataset_id or "/" in dataset_id:
            raise ValueError("Pass a dataset_id without project prefix.")
        return bigquery.DatasetReference(self.project(project_id), dataset_id)

    def table_ref(
        self, dataset_id: str, table_id: str, project_id: str | None
    ) -> bigquery.TableReference:
        if not table_id or "." in table_id or "/" in table_id or "*" in table_id:
            raise ValueError(
                "Pass a single table_id without project or dataset prefix."
            )
        return self.dataset_ref(dataset_id, project_id).table(table_id)

    def get_dataset(self, dataset_id: str, project_id: str | None) -> dict:
        dataset = self.client.get_dataset(
            self.dataset_ref(dataset_id, project_id), timeout=30
        )
        return {
            "project_id": dataset.project,
            "dataset_id": dataset.dataset_id,
            "location": dataset.location,
            "description": dataset.description,
            "labels": dataset.labels,
            "created": json_value(dataset.created),
        }

    def list_tables(
        self,
        dataset_id: str,
        project_id: str | None,
        page_size: int,
        page_token: str | None,
    ) -> dict:
        return page_payload(
            self.client.list_tables(
                self.dataset_ref(dataset_id, project_id),
                page_size=page_size,
                page_token=page_token,
                timeout=30,
            ),
            lambda t: {
                "table_id": t.table_id,
                "dataset_id": t.dataset_id,
                "project_id": t.project,
                "table_type": t.table_type,
            },
        )

    def get_table(self, dataset_id: str, table_id: str, project_id: str | None) -> dict:
        table = self.client.get_table(
            self.table_ref(dataset_id, table_id, project_id), timeout=30
        )
        return {
            "project_id": table.project,
            "dataset_id": table.dataset_id,
            "table_id": table.table_id,
            "table_type": table.table_type,
            "description": table.description,
            "num_rows": table.num_rows,
            "num_bytes": table.num_bytes,
            "location": table.location,
            "schema": schema_payload(table.schema),
            "labels": table.labels,
            "time_partitioning": table.time_partitioning.to_api_repr()
            if table.time_partitioning
            else None,
            "range_partitioning": table.range_partitioning.to_api_repr()
            if table.range_partitioning
            else None,
            "clustering_fields": table.clustering_fields,
            "require_partition_filter": table.require_partition_filter,
        }

    def preview_table(
        self,
        dataset_id: str,
        table_id: str,
        project_id: str | None,
        page_size: int,
        page_token: str | None,
    ) -> dict:
        table = self.client.get_table(
            self.table_ref(dataset_id, table_id, project_id), timeout=30
        )
        if table.table_type != "TABLE":
            raise ValueError(
                "Preview supports physical tables; use run_query for views and external tables."
            )
        rows = self.client.list_rows(
            table,
            page_size=page_size,
            max_results=page_size,
            page_token=page_token,
            timeout=30,
        )
        result = page_payload(rows, json_value)
        return {
            "schema": schema_payload(table.schema),
            "rows": result["items"],
            "next_page_token": result["next_page_token"],
            "total_rows": rows.total_rows,
        }

    def query_config(
        self,
        parameters: list[QueryParameter] | None,
        maximum_bytes_billed: int | None,
        *,
        dry_run: bool,
    ) -> bigquery.QueryJobConfig:
        limit = (
            self.settings.max_bytes_billed
            if maximum_bytes_billed is None
            else maximum_bytes_billed
        )
        if limit <= 0 or limit > self.settings.max_bytes_billed:
            raise CostLimitError(
                "Requested byte limit exceeds the configured ceiling or is not positive."
            )
        params = parameters or []
        if len({p.name for p in params}) != len(params):
            raise ValueError("Query parameter names must be unique.")
        return bigquery.QueryJobConfig(
            dry_run=dry_run,
            use_legacy_sql=False,
            maximum_bytes_billed=limit,
            use_query_cache=not dry_run,
            query_parameters=[
                bigquery.ScalarQueryParameter(p.name, p.type, p.value) for p in params
            ],
            labels={"application": "flin-bigquery-mcp"},
        )

    def validate_query(
        self,
        sql: str,
        project_id: str | None,
        location: str | None,
        parameters: list[QueryParameter] | None,
        maximum_bytes_billed: int | None,
    ) -> tuple[Any, Any]:
        if not sql.strip():
            raise ValueError("SQL must not be empty.")
        config = self.query_config(parameters, maximum_bytes_billed, dry_run=True)
        job = self.client.query(
            sql,
            project=self.project(project_id),
            location=self.location(location),
            job_config=config,
            timeout=30,
        )
        # Let Google's GoogleSQL parser classify the entire statement. Regex
        # prefix checks cannot safely distinguish scripts, comments and CTEs.
        if job.statement_type != "SELECT":
            raise QueryRejectedError(
                "Only a single SELECT query is allowed; scripts and writes are rejected."
            )
        if (
            job.total_bytes_processed is not None
            and job.total_bytes_processed > config.maximum_bytes_billed
        ):
            raise CostLimitError("Dry-run estimate exceeds the query byte limit.")
        return job, config

    def dry_run_query(
        self,
        sql: str,
        project_id: str | None,
        location: str | None,
        parameters: list[QueryParameter] | None,
        maximum_bytes_billed: int | None,
    ) -> dict:
        job, config = self.validate_query(
            sql, project_id, location, parameters, maximum_bytes_billed
        )
        return {
            "dry_run": True,
            "statement_type": job.statement_type,
            "project_id": self.project(project_id),
            "location": job.location,
            "estimated_bytes_processed": job.total_bytes_processed,
            "maximum_bytes_billed": config.maximum_bytes_billed,
            "schema": schema_payload(job.schema or []),
        }

    def run_query(
        self,
        sql: str,
        project_id: str | None,
        location: str | None,
        parameters: list[QueryParameter] | None,
        maximum_bytes_billed: int | None,
    ) -> dict:
        dry_job, config = self.validate_query(
            sql, project_id, location, parameters, maximum_bytes_billed
        )
        config.dry_run = False
        config.use_query_cache = True
        job = self.client.query(
            sql,
            project=self.project(project_id),
            location=dry_job.location or self.location(location),
            job_config=config,
            timeout=30,
            job_retry=None,
        )
        # Submit once and return immediately. Fetch/poll using the returned job
        # reference; retrying this tool can create another billable job.
        return {
            "job_id": job.job_id,
            "project_id": job.project,
            "location": job.location,
            "state": job.state,
            "maximum_bytes_billed": config.maximum_bytes_billed,
            "estimated_bytes_processed": dry_job.total_bytes_processed,
            "next_tool": "get_query_results",
        }

    def get_query_results(
        self,
        job_id: str,
        project_id: str | None,
        location: str | None,
        page_size: int,
        page_token: str | None,
    ) -> dict:
        job = self.client.get_job(
            job_id,
            project=self.project(project_id),
            location=self.location(location),
            timeout=30,
        )
        if not isinstance(job, bigquery.QueryJob):
            raise ValueError("The job is not a query job.")
        result = {
            "job_id": job.job_id,
            "project_id": job.project,
            "location": job.location,
            "state": job.state,
        }
        if job.error_result:
            return {
                **result,
                "ok": False,
                "error": {"reason": job.error_result.get("reason", "query_failed")},
            }
        if job.state != "DONE":
            return {
                **result,
                "ok": True,
                "job_complete": False,
                "next_tool": "get_query_results",
            }
        if job.statement_type != "SELECT" or job.destination is None:
            raise QueryRejectedError("Only SELECT result tables are supported.")
        # Use tabledata.list consistently for every page. Tokens from
        # jobs.getQueryResults must not be mixed with tabledata.list tokens.
        rows = self.client.list_rows(
            job.destination,
            page_size=page_size,
            max_results=page_size,
            page_token=page_token,
            timeout=30,
        )
        page = page_payload(rows, json_value)
        return {
            **result,
            "ok": True,
            "job_complete": True,
            "schema": schema_payload(rows.schema),
            "rows": page["items"],
            "next_page_token": page["next_page_token"],
            "total_rows": rows.total_rows,
            "total_bytes_processed": job.total_bytes_processed,
            "total_bytes_billed": job.total_bytes_billed,
            "cache_hit": job.cache_hit,
        }
