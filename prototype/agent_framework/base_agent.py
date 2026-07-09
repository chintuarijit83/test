"""
Common scaffolding shared by every agent. No LLM by default - every agent
built so far (Hierarchical Supervisor, Data Agent) is confirmed
deterministic. If a future agent genuinely needs LLM reasoning (e.g.
Detection Agent / Deep Analysis Agent's ReAct loops), it subclasses this
and adds its own reasoning loop on top - the base contract (name + run())
stays the same either way.
"""

from interfaces.agent_interface import AgentInterface


class BaseAgent(AgentInterface):
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def run(self, *args, **kwargs):
        raise NotImplementedError(f"{self._name} must implement run()")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self._name!r}>"
