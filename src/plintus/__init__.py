"""plintus — fast extensible Python linter for context-dependent rules."""

from __future__ import annotations

from plintus.api import Diagnostic, Fix, Rule, RuleContext, Severity, resolve_call_name

__version__ = "0.1.0"
API_VERSION = "1"

__all__ = [
    "API_VERSION",
    "Diagnostic",
    "Fix",
    "Rule",
    "RuleContext",
    "Severity",
    "resolve_call_name",
    "__version__",
]
