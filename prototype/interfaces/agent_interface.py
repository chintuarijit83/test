"""
Every agent (Hierarchical Supervisor, Data Agent, and future Feature
Curation / Comparison / Statistical Testing / Real-Time Signal / Rules-Policy
agents) implements this. Confirmed by the team: these agents are
deterministic code, not LLM reasoning loops - run() is a plain method call,
not a prompt.
"""

from abc import ABC, abstractmethod


class AgentInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Official component name, e.g. 'Hierarchical Supervisor', 'Data Agent'."""

    @abstractmethod
    def run(self, *args, **kwargs):
        """Execute this agent's responsibility and return its result."""
