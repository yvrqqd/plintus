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
    """Enforce quote style for dict literals and subscript field access.

    Covers dict keys/values (including logging ``extra={...}`` slots) and
    string indexes like ``obj['key']`` via ``dict_quotes`` (default single).
    Message strings outside those contexts are Q002.
    Skips literals that cannot safely use the configured quote style
    (e.g. f\"...'{id}'...\").
    """

    id = "Q001"
    message = "Dict / subscript string literals should use the configured quote style"
    severity = Severity.WARNING
    targets = ("string",)

    def check(self, ctx: RuleContext) -> None:
        wanted = ctx.config.get("dict_quotes", "single")
        for node in ctx.nodes:
            if not (ctx.in_dict_string(node) or ctx.is_subscript_index_string(node)):
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
                f"Use {wanted} quotes for dict / subscript string literals",
                fix=fix,
            )


class MessageQuotes(Rule):
    """Enforce quote style for raise / logging / print / json_response messages.

    Does not own dict literals or subscript indexes (``extra={...}`` slots and
    ``obj['key']`` stay under Q001 / ``dict_quotes``).
    """

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
            # Dict / subscript field names use Q001, not Q002
            if ctx.in_dict_string(node) or ctx.is_subscript_index_string(node):
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
