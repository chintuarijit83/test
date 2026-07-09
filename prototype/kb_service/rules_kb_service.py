"""
Rules KB service.

Rule definitions are S3-CSV-backed documents (not structured data), so a
plain semantic `retrieve()` is the right call - not NL2SQL. Contents per
rule (confirmed from today's discussion): definition, threshold, severity,
applicable_portfolios.
"""

import csv
import io
import json
from typing import Optional

import boto3

import config
from interfaces.kb_service_interface import KBServiceInterface
from models import Rule

# Must match kb_seed/rules_seed.csv's header order exactly.
_CSV_COLUMNS = [
    "rule_id", "name", "description", "threshold", "severity",
    "applicable_portfolios", "skill_type", "required_agents",
]
_LIST_SEP = "|"  # matches kb_seed/rules_seed.csv's convention for multi-value cells


class RulesKBService(KBServiceInterface):
    def __init__(self):
        self._client = None

    @property
    def kb_id_configured(self) -> bool:
        return bool(config.RULES_KB_ID)

    def _client_lazy(self):
        if self._client is None:
            self._client = boto3.client("bedrock-agent-runtime", region_name=config.AWS_REGION)
        return self._client

    def _parse_rule_chunk(self, text: str) -> Optional[Rule]:
        """Rule content is seeded as plain CSV rows (kb_seed/rules_seed.csv) -
        not JSON. A retrieved chunk's exact shape depends on how the KB was
        configured to ingest that CSV (one row per chunk vs. something else) -
        this handles the two likely shapes: a JSON object, or a raw
        comma-separated row matching the seed file's column order. Verify
        against what a real retrieve() call actually returns and adjust here
        if neither matches.
        """
        rule = self._parse_as_json(text)
        if rule is not None:
            return rule
        return self._parse_as_csv_row(text)

    def _parse_as_json(self, text: str) -> Optional[Rule]:
        try:
            data = json.loads(text)
            return Rule(
                rule_id=str(data["rule_id"]),
                name=data.get("name", ""),
                description=data.get("description", ""),
                threshold=data.get("threshold"),
                severity=data.get("severity", "MEDIUM"),
                applicable_portfolios=data.get("applicable_portfolios", []),
                skill_type=data.get("skill_type", "UNKNOWN"),
                required_agents=data.get("required_agents", []),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def _parse_as_csv_row(self, text: str) -> Optional[Rule]:
        try:
            reader = csv.reader(io.StringIO(text.strip()))
            row = next(reader)
            if len(row) != len(_CSV_COLUMNS):
                return None
            data = dict(zip(_CSV_COLUMNS, row))
            threshold = float(data["threshold"]) if data["threshold"] else None
            return Rule(
                rule_id=data["rule_id"],
                name=data["name"],
                description=data["description"],
                threshold=threshold,
                severity=data["severity"] or "MEDIUM",
                applicable_portfolios=[p for p in data["applicable_portfolios"].split(_LIST_SEP) if p],
                skill_type=data["skill_type"] or "UNKNOWN",
                required_agents=[a for a in data["required_agents"].split(_LIST_SEP) if a],
            )
        except (StopIteration, ValueError):
            return None

    def query(self, client_id: str) -> list:
        """Retrieve the fraud rule set applicable to a specific client."""
        if config.RULES_KB_MOCK:
            return self._mock_rules_for_client(client_id)

        if not self.kb_id_configured:
            raise RuntimeError("RULES_KB_ID is not configured - set it in .env or the environment")

        response = self._client_lazy().retrieve(
            knowledgeBaseId=config.RULES_KB_ID,
            retrievalQuery={"text": f"fraud rules applicable to client {client_id}"},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 20}},
        )

        rules = []
        for result in response.get("retrievalResults", []):
            text = result.get("content", {}).get("text", "")
            rule = self._parse_rule_chunk(text)
            if rule and (not rule.applicable_portfolios or client_id in rule.applicable_portfolios):
                rules.append(rule)
        return rules

    def _mock_rules_for_client(self, client_id: str) -> list:
        all_rules = [
            Rule(
                rule_id="1",
                name="Unexplained application volume spike",
                description="Total applications by hour/day/channel vs expected baseline",
                threshold=None,  # comes from the Baseline Matrix's UCL, not a fixed number
                severity="HIGH",
                applicable_portfolios=[],  # empty = applies to all portfolios
                skill_type="UCL",
                required_agents=["Data Agent", "Feature Curation Agent", "Comparison Agent", "Statistical Testing Agent"],
            ),
            Rule(
                rule_id="3",
                name="IP/device/email/phone velocity",
                description="Many applications from same/related IP, device, email domain, phone prefix",
                threshold=None,
                severity="HIGH",
                applicable_portfolios=[],
                skill_type="VENDOR_CODE_MATCH",
                required_agents=["Data Agent", "Comparison Agent"],
            ),
            Rule(
                rule_id="5",
                name="Small segment becomes unusually large",
                description="Segment share jumps from normal low % to much higher %",
                threshold=None,
                severity="MEDIUM",
                applicable_portfolios=["SYF_BNPL", "CARE_CREDIT"],  # NOT applicable for Amazon PL
                skill_type="PSI",
                required_agents=["Data Agent", "Feature Curation Agent", "Comparison Agent", "Statistical Testing Agent"],
            ),
        ]
        return [r for r in all_rules if not r.applicable_portfolios or client_id in r.applicable_portfolios]
