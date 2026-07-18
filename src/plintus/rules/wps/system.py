"""WPS system rules."""

from __future__ import annotations

from plintus.api import Rule, RuleContext
from plintus.rules.wps._factory import make_rule
from plintus.rules.wps.catalog_data import MESSAGES


def _check_wps000(ctx: RuleContext) -> None:
    """Reserved for internal errors; never emitted by normal rule runs."""
    return


def register() -> list[Rule]:
    return [make_rule('WPS000', MESSAGES['WPS000'], (), _check_wps000)]
