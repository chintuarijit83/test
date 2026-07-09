"""
Data Agent.

Retrieves data from Redshift and creates the baseline matrix, for one
client + rule. Confirmed pattern:

    Data Agent -> Metrics/Schema KB ("how do I build the baseline matrix
    for Client X using Rule Y?") -> KB returns SQL template + metric
    definition -> Data Agent executes that SQL via the Hard Logic Code
    Tool (RedshiftExecutor) -> Redshift -> Baseline Matrix

Only rules that MoE Gate has dispatched to "Data Agent" reach run() -
that decision happens upstream.
"""

from datetime import datetime, timezone

from agent_framework.base_agent import BaseAgent
from hard_logic_tools.redshift_executor import RedshiftExecutor
from kb_service.metrics_schema_kb_service import MetricsSchemaKBService
from models import BaselineMatrix, Rule


class DataAgent(BaseAgent):
    def __init__(self, metrics_schema_kb: MetricsSchemaKBService = None, redshift: RedshiftExecutor = None):
        super().__init__(name="Data Agent")
        self._metrics_schema_kb = metrics_schema_kb or MetricsSchemaKBService()
        self._redshift = redshift or RedshiftExecutor()

    def run(self, client_id: str, rule: Rule) -> BaselineMatrix:
        sql_template = self._metrics_schema_kb.query(client_id, rule.rule_id)
        rows = self._redshift.execute(sql_template.sql)

        return BaselineMatrix(
            client_id=client_id,
            rule_id=rule.rule_id,
            rows=rows,
            sql_used=sql_template.sql,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
