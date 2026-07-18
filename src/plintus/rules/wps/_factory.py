"""Build Rule instances from id/message/targets/checker."""

from __future__ import annotations

from typing import Callable, Sequence

from plintus.api import Rule, RuleContext, Severity

# Attribute holding the closed-over checker for cache hashing (see engine.rules_hash).
_CHECKER_ATTR = "_plintus_checker"


def make_rule(
    code: str,
    message: str,
    targets: Sequence[str],
    checker: Callable[[RuleContext], None],
    *,
    severity: Severity = Severity.ERROR,
) -> Rule:
    class _WpsRule(Rule):
        def check(self, ctx: RuleContext) -> None:
            checker(ctx)

    _WpsRule.__name__ = code
    _WpsRule.__qualname__ = code
    inst = _WpsRule()
    inst.id = code
    inst.message = message
    inst.severity = severity
    inst.targets = tuple(targets)
    # Distinct per-rule source for cache invalidation (wrapper `check` is shared).
    setattr(inst, _CHECKER_ATTR, checker)
    return inst
