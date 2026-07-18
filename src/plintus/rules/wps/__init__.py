"""WPS (wemake-python-styleguide) builtin pack."""

from __future__ import annotations

from plintus.api import Rule
from plintus.rules.wps import (
    best_practices,
    complexity,
    consistency,
    naming,
    oop,
    refactoring,
    system,
)


def register_wps() -> list[Rule]:
    rules: list[Rule] = []
    rules.extend(system.register())
    rules.extend(naming.register())
    rules.extend(complexity.register())
    rules.extend(consistency.register())
    rules.extend(best_practices.register())
    rules.extend(refactoring.register())
    rules.extend(oop.register())
    return rules
