"""ORD001 — enforce keyword argument order for configured calls (sibling order)."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, Severity, resolve_call_name


class CallArgOrder(Rule):
    """If call-arg-order is configured, require keyword args to appear in that order."""

    id = "ORD001"
    message = "Keyword arguments are out of the required order"
    severity = Severity.WARNING
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        order_map: dict[str, list[str]] = dict(ctx.config.get("call_arg_order", {}) or {})
        if not order_map:
            return
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if not name or name not in order_map:
                continue
            expected = order_map[name]
            keywords = _keyword_names(ctx, node)
            # relative order of keywords that appear in expected
            filtered = [k for k in keywords if k in expected]
            expected_filtered = [k for k in expected if k in filtered]
            if filtered != expected_filtered:
                ctx.report(
                    node,
                    f"Keyword arguments for {name} should follow order: {', '.join(expected)}",
                )


def _keyword_names(ctx: RuleContext, call_node) -> list[str]:
    names: list[str] = []
    for child in ctx.children(call_node):
        if child.kind == "keyword_argument":
            kids = ctx.children(child)
            for k in kids:
                if k.kind == "identifier":
                    names.append(k.text())
                    break
        elif child.kind == "argument_list":
            for arg in ctx.children(child):
                if arg.kind == "keyword_argument":
                    kids = ctx.children(arg)
                    for k in kids:
                        if k.kind == "identifier":
                            names.append(k.text())
                            break
    return names
