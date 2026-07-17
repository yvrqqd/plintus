"""BAN001 — ban configured call names (not bugbear B001)."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, Severity, resolve_call_name


class BannedCalls(Rule):
    id = "BAN001"
    message = "Banned call"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        banned = set(ctx.config.get("banned_calls", []))
        if not banned:
            return
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if name and name in banned:
                ctx.report(node, f"Call to banned function '{name}' is not allowed")
