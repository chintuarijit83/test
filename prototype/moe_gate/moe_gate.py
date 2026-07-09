"""
MoE Gate.

Deterministic, no LLM. Decides which agents - and, at the finer grain
confirmed today, which specific skill (Hard Logic tool) - need to spin up
per dispatched rule. This is a lookup off each Rule's own fields
(required_agents, skill_type), not a decision MoE Gate makes up on the
fly - "invokes only the experts each rule needs," controlling cost,
latency, and blast radius.
"""

from models import DispatchPlan, Rule


class MoEGate:
    def gate(self, client_id: str, dispatched_rules: list) -> DispatchPlan:
        agents_by_rule = {
            rule.rule_id: {"agents": rule.required_agents, "skill_type": rule.skill_type}
            for rule in dispatched_rules
        }
        return DispatchPlan(
            client_id=client_id,
            applicable_rules=dispatched_rules,
            agents_by_rule=agents_by_rule,
        )
