"""
Typed data contracts shared across the Supervisor, Rule Dispatcher / MoE Gate,
and Data Agent. Kept dependency-free (stdlib dataclasses only) so each piece
is independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Rule:
    """One fraud rule, as retrieved from the Rules KB for a given client."""

    rule_id: str
    name: str
    description: str
    threshold: Optional[float]
    severity: str  # e.g. "LOW" / "MEDIUM" / "HIGH" / "CRITICAL"
    applicable_portfolios: list  # client_ids this rule applies to
    skill_type: str  # which Hard Logic tool this rule needs, e.g. "UCL", "PSI", "RATE_RATIO"
    required_agents: list  # e.g. ["Data Agent", "Feature Curation Agent", "Comparison Agent"]


@dataclass(frozen=True)
class DispatchPlan:
    """Output of the Rule Dispatcher + MoE Gate for one client."""

    client_id: str
    applicable_rules: list  # list[Rule], already filtered to this client
    # rule_id -> list of agents/skills that need to spin up for that rule
    agents_by_rule: dict


@dataclass(frozen=True)
class SqlTemplate:
    """What the Metrics/Schema KB hands back for a natural-language data question."""

    sql: str
    table_names: list
    joins: list
    metric_definition: str
    schema_notes: Optional[str] = None


@dataclass(frozen=True)
class BaselineMatrix:
    """Result of Data Agent executing the KB-supplied SQL against Redshift."""

    client_id: str
    rule_id: str
    rows: list  # raw rows returned from Redshift
    sql_used: str
    generated_at: str
