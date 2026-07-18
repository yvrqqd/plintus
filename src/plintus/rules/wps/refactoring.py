"""WPS refactoring rules (WPS5xx)."""

from __future__ import annotations

import re

from plintus.api import Rule, RuleContext, resolve_call_name
from plintus.rules.wps import helpers as H
from plintus.rules.wps._factory import make_rule
from plintus.rules.wps.catalog_data import MESSAGES


def _check_wps500(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement", "while_statement")):
        if " else:" in node.text() and "break" not in node.text():
            ctx.report(node, "else without break in loop")


def _check_wps501(ctx: RuleContext) -> None:
    for node in ctx.document.select(("try_statement",)):
        has_finally = "finally:" in node.text()
        has_except = "except" in node.text()
        if has_finally and not has_except:
            ctx.report(node, "finally without except")


def _check_wps502(ctx: RuleContext) -> None:
    for node in ctx.document.select(("if_statement",)):
        if re.search(r"if\s+(True|False)\s*:", node.text()):
            ctx.report(node, "Simplifiable if condition")


def _check_wps503(ctx: RuleContext) -> None:
    for node in ctx.document.select(("if_statement",)):
        if " else:" in node.text() and node.text().count("return") >= 2:
            ctx.report(node, "Useless else in returning function")


def _check_wps504(ctx: RuleContext) -> None:
    for node in ctx.document.select(("if_statement",)):
        if re.search(r"if\s+not\s+", node.text()) and " else:" in node.text():
            ctx.report(node, "Negated condition with else")


def _check_wps505(ctx: RuleContext) -> None:
    for node in ctx.document.select(("try_statement",)):
        nested = [
            n
            for n in H.walk_subtree(ctx, node)
            if n.kind == "try_statement" and n.id != node.id
        ]
        if nested:
            ctx.report(nested[0], "Nested try block")


def _check_wps506(ctx: RuleContext) -> None:
    for node in ctx.document.select(("lambda",)):
        text = node.text().strip()
        if re.match(r"lambda\s+(\w+)\s*:\s*(\w+)\(\1\)\s*$", text):
            ctx.report(node, "Useless proxy lambda")
        if re.match(r"lambda\s*:\s*\w+\(\)\s*$", text):
            ctx.report(node, "Useless proxy lambda")


def _check_wps507(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator", "call")):
        text = node.text()
        if "len(" in text and ("== 0" in text or "!= 0" in text or "> 0" in text):
            ctx.report(node, "Unpythonic zero-length compare")


def _check_wps508(ctx: RuleContext) -> None:
    for node in ctx.document.select(("unary_operator", "not_operator")):
        if node.text().strip().startswith("not ") and any(
            op in node.text() for op in ("==", "!=", "<", ">", "is", "in")
        ):
            ctx.report(node, "not with compare expression")


def _check_wps509(ctx: RuleContext) -> None:
    for node in ctx.document.select(("conditional_expression",)):
        if any(a.kind == "conditional_expression" for a in ctx.ancestors(node)):
            ctx.report(node, "Nested ternary expression")
        if H.count_kind_in_subtree(ctx, node, "conditional_expression") > 1:
            ctx.report(node, "Nested ternary expression")


def _check_wps510(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        text = node.text()
        if re.search(r"\bin\s*\[", text) or re.search(r"\bin\s*\(", text):
            ctx.report(node, "in with static list/tuple; use set")


def _check_wps515(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = resolve_call_name(ctx.document, node)
        if name != "open":
            continue
        if not any(a.kind == "with_statement" for a in ctx.ancestors(node)):
            ctx.report(node, "open() without context manager")


def _check_wps516(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator", "call")):
        if "type(" in node.text() and ("==" in node.text() or " is " in node.text()):
            ctx.report(node, "Comparing types with type()")


def _check_wps518(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement",)):
        if re.search(r"for\s+\w+\s+in\s+range\(\s*len\(", node.text()):
            ctx.report(node, "Implicit enumerate(); use enumerate()")


def _check_wps520(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        text = node.text()
        if re.search(r"==\s*(None|False|True|\[\]|\{\})", text) or re.search(
            r"!=\s*(None|False|True|\[\]|\{\})", text
        ):
            ctx.report(node, "Comparing with explicit falsy constant")


def _check_wps521(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        if re.search(r"\bis\b", node.text()) and not re.search(
            r"\bis\s+(not\s+)?None\b", node.text()
        ):
            if any(x in node.text() for x in ("True", "False", '"', "'")):
                ctx.report(node, "Comparing values with is/is not")


def _check_wps531(ctx: RuleContext) -> None:
    for node in ctx.document.select(("if_statement",)):
        text = node.text()
        if "return True" in text and "return False" in text:
            ctx.report(node, "If that simply returns booleans")


def _check_wps523(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        if re.match(r"\w+\s*,\s*\w+\s*=\s*\w+\s*,\s*\w+", node.text()):
            ctx.report(node, MESSAGES['WPS523'])


def _check_wps535(ctx: RuleContext) -> None:
    for node in ctx.document.select(("match_statement",)):
        cases = [n.text() for n in H.walk_subtree(ctx, node) if n.kind == "case_clause"]
        if len(cases) != len(set(cases)):
            ctx.report(node, MESSAGES['WPS535'])


_EXPLICIT: dict[str, tuple] = {
    'WPS500': (_check_wps500, ()),
    'WPS501': (_check_wps501, ()),
    'WPS502': (_check_wps502, ()),
    'WPS503': (_check_wps503, ()),
    'WPS504': (_check_wps504, ()),
    'WPS505': (_check_wps505, ()),
    'WPS506': (_check_wps506, ()),
    'WPS507': (_check_wps507, ()),
    'WPS508': (_check_wps508, ()),
    'WPS509': (_check_wps509, ()),
    'WPS510': (_check_wps510, ()),
    'WPS515': (_check_wps515, ("call",)),
    'WPS516': (_check_wps516, ()),
    'WPS518': (_check_wps518, ()),
    'WPS520': (_check_wps520, ()),
    'WPS521': (_check_wps521, ()),
    'WPS523': (_check_wps523, ()),
    'WPS531': (_check_wps531, ()),
    'WPS535': (_check_wps535, ()),
}


def register() -> list[Rule]:
    # Only register implemented/partial checkers — planned stubs stay in catalog only.
    return [
        make_rule(code, MESSAGES[code], targets, checker)
        for code, (checker, targets) in _EXPLICIT.items()
    ]
