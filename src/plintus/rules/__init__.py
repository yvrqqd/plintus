"""Built-in rule pack."""

from __future__ import annotations

from plintus.api import Rule
from plintus.rules.banned_calls import BannedCalls
from plintus.rules.call_order import CallArgOrder
from plintus.rules.quotes import DictQuotes, MessageQuotes
from plintus.rules.require_decorator import RequireDecorator


def register() -> list[Rule]:
    return [
        DictQuotes(),
        MessageQuotes(),
        CallArgOrder(),
        BannedCalls(),
        RequireDecorator(),
    ]
