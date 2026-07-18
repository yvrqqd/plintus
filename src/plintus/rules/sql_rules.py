"""SQL001 — no f-string / .format SQL in execute calls (db.mdc)."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import (
    call_name_matches,
    is_fstring_node,
    keyword_args,
    looks_like_sql_dao_call,
    positional_args,
)

_SQL_KWARG_NAMES = frozenset({"query", "sql", "statement", "operation"})


def _flag_sql_arg(ctx: RuleContext, sql_arg) -> bool:
    """Report if ``sql_arg`` is an f-string or ``.format`` call. Returns True if flagged."""
    if sql_arg.kind == "string" and is_fstring_node(sql_arg):
        ctx.report(sql_arg, "Do not use f-string SQL; use parameterized queries")
        return True
    if sql_arg.kind == "call":
        inner = resolve_call_name(ctx.document, sql_arg)
        if call_name_matches(inner, "format"):
            ctx.report(sql_arg, "Do not use str.format for SQL; use parameterized queries")
            return True
        kids = ctx.children(sql_arg)
        if kids and kids[0].kind == "attribute":
            attr_text = kids[0].text()
            if attr_text.endswith(".format"):
                ctx.report(sql_arg, "Do not use str.format for SQL; use parameterized queries")
                return True
    return False


class NoFormatSql(Rule):
    id = "SQL001"
    message = "Do not build SQL with f-strings or str.format; use parameterized queries"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if not looks_like_sql_dao_call(name):
                continue
            candidates = list(positional_args(ctx, node)[:1])
            kwargs = keyword_args(ctx, node)
            for key in _SQL_KWARG_NAMES:
                if key in kwargs:
                    candidates.append(kwargs[key])
            for sql_arg in candidates:
                if _flag_sql_arg(ctx, sql_arg):
                    break
