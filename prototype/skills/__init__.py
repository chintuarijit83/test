"""
Individual skills - concrete SkillInterface implementations, one per
Hard Logic test type (UCL, PSI, chi-square, rate-ratio, spike test,
thresholding). MoE Gate selects which of these to invoke per rule, via
each Rule's skill_type field, looked up through registry.py.

No concrete skills exist yet - they belong to Statistical Testing Agent,
which hasn't been built (current scope stops at Data Agent). See
registry.py for how to add the first one.
"""
