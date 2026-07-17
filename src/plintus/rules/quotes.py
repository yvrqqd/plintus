"""Q001 / Q002 — context-dependent quote styles."""

from __future__ import annotations

from plintus.api import Fix, Rule, RuleContext, Severity
from plintus.rules.string_utils import (
    can_switch_quotes,
    is_message_context,
    parse_string_literal,
    quote_style,
    requote,
)


class DictQuotes(Rule):
    """Enforce quote style for strings inside dict literals.

    Defers to Q002 for *values* under message / user-facing calls
    (logging, raise, json_response, …). Dict *keys* stay under Q001.
    Skips literals that cannot safely use the configured quote style
    (e.g. f\"...'{id}'...\").
    """

    id = "Q001"
    message = "Dict string literals should use the configured quote style"
    severity = Severity.WARNING
    targets = ("string",)

    def check(self, ctx: RuleContext) -> None:
        wanted = ctx.config.get("dict_quotes", "single")
        message_calls = list(ctx.config.get("message_calls", []))
        for node in ctx.nodes:
            if not ctx.in_dict_string(node):
                continue
            call_name = ctx.enclosing_call_name(node)
            in_message = is_message_context(
                call_name, message_calls, ctx.is_raise_message(node)
            )
            # Message calls own dict *values*; keys still use dict quote style
            if in_message and ctx.is_dict_value(node):
                continue
            text = node.text()
            parsed = parse_string_literal(text)
            if parsed is None:
                continue
            _, quote, _ = parsed
            if quote_style(quote) == wanted:
                continue
            if not can_switch_quotes(text, wanted):
                continue
            result = requote(text, wanted)
            fix = None
            if result is not None:
                new_text, safe = result
                fix = Fix.replace(node, new_text, safety="safe" if safe else "unsafe")
            ctx.report(
                node,
                f"Use {wanted} quotes for dict string literals",
                fix=fix,
            )


class MessageQuotes(Rule):
    """Enforce quote style for raise / logging / print / json_response messages."""

    id = "Q002"
    message = "Message strings should use the configured quote style"
    severity = Severity.WARNING
    targets = ("string",)

    def check(self, ctx: RuleContext) -> None:
        wanted = ctx.config.get("message_quotes", "double")
        message_calls = list(ctx.config.get("message_calls", []))
        for node in ctx.nodes:
            call_name = ctx.enclosing_call_name(node)
            is_raise = ctx.is_raise_message(node)
            if not is_message_context(call_name, message_calls, is_raise):
                continue
            # Dict keys under json_response are not "messages"
            if ctx.is_dict_key(node):
                continue
            text = node.text()
            parsed = parse_string_literal(text)
            if parsed is None:
                continue
            _, quote, _ = parsed
            if quote_style(quote) == wanted:
                continue
            if not can_switch_quotes(text, wanted):
                continue
            result = requote(text, wanted)
            fix = None
            if result is not None:
                new_text, safe = result
                fix = Fix.replace(node, new_text, safety="safe" if safe else "unsafe")
            ctx.report(
                node,
                f"Use {wanted} quotes for message strings",
                fix=fix,
            )
