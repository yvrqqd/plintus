"""ORD001 — enforce keyword argument order for configured calls (sibling order)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from plintus.api import Fix, Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import call_argument_list, utf8_slice

if TYPE_CHECKING:
    from plintus.document import Node


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
            keywords = _keyword_nodes(ctx, node)
            names = [k[0] for k in keywords]
            filtered = [k for k in names if k in expected]
            expected_filtered = [k for k in expected if k in filtered]
            if filtered == expected_filtered:
                continue
            fix = _reorder_keywords_fix(ctx, node, expected)
            ctx.report(
                node,
                f"Keyword arguments for {name} should follow order: {', '.join(expected)}",
                fix=fix,
            )


def _keyword_nodes(ctx: RuleContext, call_node) -> list[tuple[str, "Node"]]:
    """Return ``(name, keyword_argument node)`` in source order."""
    out: list[tuple[str, Node]] = []
    args = call_argument_list(ctx, call_node)
    if args is None:
        return out
    for arg in ctx.children(args):
        if arg.kind != "keyword_argument":
            continue
        for k in ctx.children(arg):
            if k.kind == "identifier":
                out.append((k.text(), arg))
                break
    return out


def _reorder_keywords_fix(ctx: RuleContext, call_node, expected: list[str]) -> Fix | None:
    """Fill keyword slots that appear in ``expected`` with sorted keyword texts."""
    args = call_argument_list(ctx, call_node)
    if args is None:
        return None
    keywords = _keyword_nodes(ctx, call_node)
    if not keywords:
        return None
    by_name = {name: node for name, node in keywords}
    present = [name for name, _ in keywords if name in expected]
    desired = [name for name in expected if name in by_name]
    if present == desired:
        return None
    # Slots = keyword nodes that are in expected, in current order.
    slots = [node for name, node in keywords if name in expected]
    texts = [by_name[name].text() for name in desired]
    if len(slots) != len(texts):
        return None
    start = slots[0].start
    end = slots[-1].end
    parts: list[str] = []
    prev = start
    for slot, text in zip(slots, texts):
        parts.append(utf8_slice(ctx.source, prev, slot.start))
        parts.append(text)
        prev = slot.end
    return Fix(start=start, end=end, replacement="".join(parts), safety="safe")
