"""
Metrics/Schema KB service.

This KB is connected to structured data (schema, table relationships), so
a natural-language question gets turned into a SQL template via NL2SQL
(`generate_query`) rather than retrieved passages. Confirmed pattern:

    "I need the SQL to build the baseline matrix for Client X using Rule Y"
    -> schema, SQL template, table names, joins, metric definition

NOTE: the exact `generate_query` request/response shape here is
implemented from AWS documentation, not tested against a live Knowledge
Base yet - verify once METRICS_SCHEMA_KB_ID is real.
"""

import boto3

import config
from interfaces.kb_service_interface import KBServiceInterface
from models import SqlTemplate


class MetricsSchemaKBService(KBServiceInterface):
    def __init__(self):
        self._client = None

    @property
    def kb_id_configured(self) -> bool:
        return bool(config.METRICS_SCHEMA_KB_ID)

    def _client_lazy(self):
        if self._client is None:
            self._client = boto3.client("bedrock-agent-runtime", region_name=config.AWS_REGION)
        return self._client

    def query(self, client_id: str, rule_id: str) -> SqlTemplate:
        if config.METRICS_SCHEMA_KB_MOCK:
            return self._mock_sql_template(client_id, rule_id)

        if not self.kb_id_configured:
            raise RuntimeError("METRICS_SCHEMA_KB_ID is not configured - set it in .env or the environment")

        question = f"I need the SQL to build the baseline matrix for Client {client_id} using Rule {rule_id}"

        response = self._client_lazy().generate_query(
            queryGenerationInput={"text": question, "type": "TEXT"},
            knowledgeBaseId=config.METRICS_SCHEMA_KB_ID,
        )

        generated = response.get("queries", [{}])[0]
        return SqlTemplate(
            sql=generated.get("sql", ""),
            table_names=generated.get("table_names", []),
            joins=generated.get("joins", []),
            metric_definition=generated.get("metric_definition", ""),
            schema_notes=generated.get("schema_notes"),
        )

    def _mock_sql_template(self, client_id: str, rule_id: str) -> SqlTemplate:
        return SqlTemplate(
            sql=(
                "select client_id, entered_date, hour(entered_dttm) as apphour, via_code, "
                "count(*) as apps from application_fact "
                f"where client_limit_amt > 0 and client_id = '{client_id}' "
                "group by client_id, entered_date, apphour, via_code"
            ),
            table_names=["application_fact"],
            joins=[],
            metric_definition=f"Hourly application volume by channel for rule {rule_id} (mock)",
            schema_notes="MOCK response - not from a real Metrics/Schema KB call",
        )
