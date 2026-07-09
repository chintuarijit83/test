"""
Every Hard Logic skill (UCL test, PSI test, rate-ratio test, chi-square,
spike test, thresholding, ...) implements this. Skills are what MoE Gate
selects per rule (rule.skill_type) - pure code, no LLM, "reliable math
stays outside the LLM."

No concrete skills exist yet (see skills/ - empty until Statistical
Testing Agent is built); this interface is here so that build follows
the same contract from the start.
"""

from abc import ABC, abstractmethod


class SkillInterface(ABC):
    @property
    @abstractmethod
    def skill_type(self) -> str:
        """Matches Rule.skill_type, e.g. 'UCL', 'PSI', 'RATE_RATIO', 'CHI_SQUARE'."""

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Run this skill's specific statistical/logic test and return a result."""
