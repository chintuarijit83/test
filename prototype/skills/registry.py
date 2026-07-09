"""
Skill registry - placeholder mechanism for N skills to be added later.

Each concrete skill (UCLSkill, PSISkill, RateRatioSkill, ChiSquareSkill,
SpikeTestSkill, ThresholdingSkill, ...) registers itself here under its
skill_type string. MoE Gate / Statistical Testing Agent then look up the
right skill by `rule.skill_type` - adding a new skill later means adding
one new file + one `@register_skill(...)` line, never touching dispatch
code.

Usage, once a real skill exists (e.g. skills/ucl_skill.py):

    from skills.registry import register_skill
    from interfaces.skill_interface import SkillInterface

    @register_skill("UCL")
    class UCLSkill(SkillInterface):
        skill_type = "UCL"
        def execute(self, *args, **kwargs):
            ...

Then elsewhere:

    from skills.registry import get_skill
    skill_cls = get_skill(rule.skill_type)
    result = skill_cls().execute(...)
"""

_SKILL_REGISTRY = {}


def register_skill(skill_type: str):
    """Class decorator - registers a SkillInterface implementation under skill_type."""

    def _decorator(skill_cls):
        if skill_type in _SKILL_REGISTRY:
            raise ValueError(f"Skill type {skill_type!r} is already registered to {_SKILL_REGISTRY[skill_type]!r}")
        _SKILL_REGISTRY[skill_type] = skill_cls
        return skill_cls

    return _decorator


def get_skill(skill_type: str):
    """Look up a registered skill class by its skill_type. Raises KeyError with
    the list of currently-known skill types if not found (helps while the
    registry is still mostly empty)."""
    try:
        return _SKILL_REGISTRY[skill_type]
    except KeyError:
        known = sorted(_SKILL_REGISTRY) or ["(none registered yet)"]
        raise KeyError(f"No skill registered for skill_type={skill_type!r}. Known: {known}")


def registered_skill_types() -> list:
    return sorted(_SKILL_REGISTRY)
