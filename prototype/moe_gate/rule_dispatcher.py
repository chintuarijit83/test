"""
Rule Dispatcher.

Deterministic, no LLM. Portfolio filtering already happened upstream (the
Hierarchical Supervisor's Rules KB query only returns rules applicable to
this client). This module's job is to organize that already-filtered
rule set for dispatch - currently a light validation/pass-through step,
with room to grow into execution ordering/grouping (e.g. if some rules
need to run before others) without changing its callers.
"""

from models import Rule


class RuleDispatcher:
    def dispatch(self, client_id: str, applicable_rules: list) -> list:
        if not applicable_rules:
            raise ValueError(f"No rules to dispatch for client_id={client_id!r}")
        # Placeholder for future ordering/grouping logic (e.g. rules with
        # shared data dependencies batched together). For now: pass through.
        return list(applicable_rules)
