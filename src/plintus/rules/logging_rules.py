"""L001–L006 — cbp-logging conventions from logging.mdc."""

from __future__ import annotations

from plintus.api import Fix, Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import (
    ALLOWED_LOG_METHODS,
    call_name_matches,
    final_segment,
    is_log_method_call,
    is_stringish,
    keyword_args,
    positional_args,
)


class LogMsgKeyword(Rule):
    """L001: when ``extra=`` is present, message must use ``msg=``, not positional."""

    id = "L001"
    message = "Pass log message as msg= keyword argument when extra= is used"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if not is_log_method_call(
                name, message_calls=list(ctx.config.get("message_calls", []))
            ):
                continue
            kwargs = keyword_args(ctx, node)
            if "extra" not in kwargs:
                continue
            pos = positional_args(ctx, node)
            if pos and is_stringish(pos[0]):
                msg_node = pos[0]
                ctx.report(
                    node,
                    "Log message must be passed as msg= keyword when extra= is used",
                    fix=Fix.replace(msg_node, f"msg={msg_node.text()}", safety="safe"),
                )


class NoPrint(Rule):
    """L002: no print() — prefer Ruff T20; keep for CBP-only profiles."""

    id = "L002"
    message = "print() is forbidden; use logging"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if call_name_matches(name, "print"):
                ctx.report(node, "print() is forbidden; use logging")


class NoBasicConfig(Rule):
    """L003: no logging.basicConfig / logging.config.dictConfig."""

    id = "L003"
    message = "Do not configure logging manually; use cbp-logging ServiceLoggerManager"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if name in ("logging.basicConfig", "basicConfig"):
                ctx.report(node, "logging.basicConfig is forbidden; use ServiceLoggerManager")
            elif name in ("logging.config.dictConfig", "dictConfig"):
                ctx.report(node, "logging.config.dictConfig is forbidden; use ServiceLoggerManager")


class NoNestedTagsExtra(Rule):
    """L004: no nested extra={'tags': ...}; put fields directly in extra."""

    id = "L004"
    message = "Do not nest context under extra={'tags': ...}; put fields directly in extra"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if not is_log_method_call(
                name, message_calls=list(ctx.config.get("message_calls", []))
            ):
                continue
            kwargs = keyword_args(ctx, node)
            extra = kwargs.get("extra")
            if extra is None or getattr(extra, "kind", None) != "dictionary":
                continue
            for child in ctx.children(extra):
                if child.kind != "pair":
                    continue
                kids = [c for c in ctx.children(child) if c.kind not in (":", ",")]
                if not kids:
                    continue
                key = kids[0]
                if key.kind == "string":
                    body = key.text().strip("'\"")
                    if body == "tags":
                        ctx.report(child, "Put correlation fields directly in extra={}, not under tags")


class GetLoggerDunderName(Rule):
    """L005: logging.getLogger(__name__) only."""

    id = "L005"
    message = "Use logging.getLogger(__name__)"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            # Only logging.getLogger / bare getLogger — not arbitrary *.getLogger
            if name not in ("getLogger", "logging.getLogger"):
                continue
            pos = positional_args(ctx, node)
            kwargs = keyword_args(ctx, node)
            if pos:
                arg = pos[0]
                if arg.kind == "identifier" and arg.text() == "__name__":
                    continue
                ctx.report(
                    node,
                    "Use logging.getLogger(__name__)",
                    fix=Fix.replace(arg, "__name__", safety="safe"),
                )
                continue
            if "name" in kwargs:
                arg = kwargs["name"]
                if arg.kind == "identifier" and arg.text() == "__name__":
                    continue
                ctx.report(
                    node,
                    "Use logging.getLogger(__name__)",
                    fix=Fix.replace(arg, "__name__", safety="safe"),
                )
                continue
            ctx.report(node, "logging.getLogger must be called with __name__")


class AllowedLogLevels(Rule):
    """L006: only debug / info / warning / error log methods."""

    id = "L006"
    message = "Use only debug, info, warning, or error log levels"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if not is_log_method_call(
                name, message_calls=list(ctx.config.get("message_calls", []))
            ):
                continue
            method = final_segment(name)
            if method in ALLOWED_LOG_METHODS:
                continue
            ctx.report(
                node,
                f"Log level {method!r} is forbidden; use debug, info, warning, or error",
            )
