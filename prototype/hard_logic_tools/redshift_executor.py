"""
Redshift executor - one Hard Logic Code Tool.

The Knowledge Base only ever hands back instructions (a SQL template).
This is what actually DOES something with those instructions - executes
SQL against Redshift. No LLM involved, by design ("reliable math stays
outside the LLM"). Future Hard Logic tools (UCL test, PSI test,
rate-ratio test, ...) live alongside this one once Statistical Testing
Agent is built - see skills/.
"""

import time
from datetime import datetime, timezone

import boto3

import config


class RedshiftExecutor:
    def __init__(self):
        self._client = None

    def _client_lazy(self):
        if self._client is None:
            self._client = boto3.client("redshift-data", region_name=config.AWS_REGION)
        return self._client

    @staticmethod
    def _field_value(field: dict):
        """Extract the scalar value from a Redshift Data API field, respecting isNull."""
        if not field or field.get("isNull"):
            return None
        for key, value in field.items():
            if key != "isNull":
                return value
        return None

    def execute(self, sql: str, poll_interval_sec: float = 1.0, timeout_sec: float = 60.0) -> list:
        if config.REDSHIFT_MOCK:
            return self._mock_rows()

        if not config.REDSHIFT_SECRET_ARN or not (config.REDSHIFT_WORKGROUP or config.REDSHIFT_CLUSTER_ID):
            raise RuntimeError(
                "Redshift is not configured - set REDSHIFT_WORKGROUP (or REDSHIFT_CLUSTER_ID) "
                "and REDSHIFT_SECRET_ARN in .env or the environment"
            )

        client = self._client_lazy()
        execute_kwargs = {"Database": config.REDSHIFT_DATABASE, "Sql": sql, "SecretArn": config.REDSHIFT_SECRET_ARN}
        if config.REDSHIFT_WORKGROUP:
            execute_kwargs["WorkgroupName"] = config.REDSHIFT_WORKGROUP
        elif config.REDSHIFT_CLUSTER_ID:
            execute_kwargs["ClusterIdentifier"] = config.REDSHIFT_CLUSTER_ID

        statement_id = client.execute_statement(**execute_kwargs)["Id"]

        elapsed = 0.0
        while elapsed < timeout_sec:
            status = client.describe_statement(Id=statement_id)
            state = status["Status"]
            if state == "FINISHED":
                break
            if state in ("FAILED", "ABORTED"):
                raise RuntimeError(f"Redshift statement {state}: {status.get('Error')}")
            time.sleep(poll_interval_sec)
            elapsed += poll_interval_sec
        else:
            raise TimeoutError(f"Redshift statement did not finish within {timeout_sec}s")

        columns = None
        rows = []
        next_token = None
        while True:
            kwargs = {"Id": statement_id}
            if next_token:
                kwargs["NextToken"] = next_token
            result = client.get_statement_result(**kwargs)
            if columns is None:
                columns = [c["name"] for c in result["ColumnMetadata"]]
            for record in result["Records"]:
                rows.append({col: self._field_value(field) for col, field in zip(columns, record)})
            next_token = result.get("NextToken")
            if not next_token:
                break

        return rows

    @staticmethod
    def _mock_rows() -> list:
        now = datetime.now(timezone.utc).isoformat()
        return [
            {"client_id": "AMAZON_PL", "entered_date": "2026-07-01", "apphour": 14, "via_code": "WEB", "apps": 62},
            {"client_id": "AMAZON_PL", "entered_date": "2026-07-01", "apphour": 15, "via_code": "WEB", "apps": 58},
            {"client_id": "AMAZON_PL", "entered_date": "2026-07-01", "apphour": 14, "via_code": "MOBILE", "apps": 41},
            {"_mock_generated_at": now},
        ]
