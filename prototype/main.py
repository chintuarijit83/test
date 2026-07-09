"""
End-to-end workflow entrypoint - run from cmd/terminal, no AWS deployment
needed.

Wires the full path built so far:

    Hierarchical Supervisor -> Rule Dispatcher -> MoE Gate -> Data Agent

Stops there for now per current scope - Feature Curation / Comparison /
Statistical Testing / Real-Time Signal agents aren't built yet.

Usage:
    python main.py --client-id AMAZON_PL
    python main.py --client-id SYF_BNPL --rule-id 5

Runs in MOCK_MODE by default (see config.py) - no AWS credentials or
Knowledge Base/Redshift setup required to try it out. Set MOCK_MODE=false
once RULES_KB_ID, METRICS_SCHEMA_KB_ID, and Redshift settings are real.
"""

import argparse
import json
from dataclasses import asdict

import config
from agents.data_agent import DataAgent
from agents.supervisor import Supervisor
from moe_gate.moe_gate import MoEGate
from moe_gate.rule_dispatcher import RuleDispatcher


def run(client_id: str, rule_id: str = None) -> dict:
    supervisor = Supervisor()
    applicable_rules = supervisor.run(client_id)

    if rule_id:
        applicable_rules = [r for r in applicable_rules if r.rule_id == rule_id]
        if not applicable_rules:
            raise ValueError(f"Rule {rule_id!r} is not applicable for client {client_id!r}")

    dispatcher = RuleDispatcher()
    dispatched_rules = dispatcher.dispatch(client_id, applicable_rules)

    gate = MoEGate()
    dispatch_plan = gate.gate(client_id, dispatched_rules)

    data_agent = DataAgent()
    baseline_matrices = []
    for rule in dispatched_rules:
        if "Data Agent" in rule.required_agents:
            matrix = data_agent.run(client_id, rule)
            baseline_matrices.append(asdict(matrix))

    return {
        "mock_mode": {
            "rules_kb": config.RULES_KB_MOCK,
            "metrics_schema_kb": config.METRICS_SCHEMA_KB_MOCK,
            "redshift": config.REDSHIFT_MOCK,
        },
        "client_id": client_id,
        "applicable_rules": [asdict(r) for r in dispatched_rules],
        "dispatch_plan": dispatch_plan.agents_by_rule,
        "baseline_matrices": baseline_matrices,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run the Rule Agent flow locally (Hierarchical Supervisor -> Rule Dispatcher -> MoE Gate -> Data Agent)"
    )
    parser.add_argument("--client-id", required=True, help="Client / portfolio identifier, e.g. AMAZON_PL")
    parser.add_argument("--rule-id", default=None, help="Optional - restrict to a single rule id")
    args = parser.parse_args()

    result = run(args.client_id, args.rule_id)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
