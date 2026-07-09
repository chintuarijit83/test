"""
Hierarchical Supervisor.

Confirmed by the team: deterministic code, NOT an LLM ("deterministic
planning... auditable routing, not LLM guesswork"). Its only job here is
to retrieve the fraud rule set applicable to a specific client from the
Rules KB. No reasoning, no free-form decisions - a lookup.
"""

from agent_framework.base_agent import BaseAgent
from kb_service.rules_kb_service import RulesKBService


class Supervisor(BaseAgent):
    def __init__(self, rules_kb: RulesKBService = None):
        super().__init__(name="Hierarchical Supervisor")
        self._rules_kb = rules_kb or RulesKBService()

    def run(self, client_id: str) -> list:
        """Retrieve the rule set applicable to this client from the Rules KB."""
        rules = self._rules_kb.query(client_id)
        if not rules:
            raise ValueError(f"No applicable rules found for client_id={client_id!r}")
        return rules
