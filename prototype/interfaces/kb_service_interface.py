"""
Every Knowledge Base service wrapper (Rules KB, Metrics/Schema KB,
Historical/Insights KB) implements this. A KB service only ever returns
instructions/definitions (rule text, SQL templates, metric definitions) -
it never executes anything itself. Execution is the Hard Logic Tool
layer's job (see hard_logic_tools/).
"""

from abc import ABC, abstractmethod


class KBServiceInterface(ABC):
    @property
    @abstractmethod
    def kb_id_configured(self) -> bool:
        """Whether this KB's real AWS id is configured (vs. still a placeholder)."""

    @abstractmethod
    def query(self, *args, **kwargs):
        """Query this knowledge base and return its structured response."""
