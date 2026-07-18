"""WPS consistency rules (WPS3xx)."""

from __future__ import annotations

import re

from plintus.api import Rule, RuleContext
from plintus.rules.wps import helpers as H
from plintus.rules.wps._factory import make_rule
from plintus.rules.wps.catalog_data import MESSAGES


def _check_wps300(ctx: RuleContext) -> None:
    for node in ctx.document.select(("import_from_statement",)):
        if re.search(r"from\s+\.", node.text()):
            ctx.report(node, "Relative import is forbidden")


def _check_wps301(ctx: RuleContext) -> None:
    for node in ctx.document.select(("import_statement",)):
        for child in ctx.children(node):
            if child.kind == "dotted_name" and "." in child.text():
                ctx.report(node, "Dotted import is forbidden; use from ... import")


def _check_wps302(ctx: RuleContext) -> None:
    for node in ctx.document.select(("string",)):
        text = node.text()
        if text.startswith(("u", "U")):
            ctx.report(node, "u-string prefix is forbidden")


def _check_wps303(ctx: RuleContext) -> None:
    for node in ctx.document.select(("integer",)):
        if "_" in node.text():
            ctx.report(node, "Underscores in numbers are forbidden")


def _check_wps304(ctx: RuleContext) -> None:
    for node in ctx.document.select(("float",)):
        text = node.text()
        if text.startswith(".") or text.endswith("."):
            ctx.report(node, "Partial float is forbidden")


def _check_wps305(ctx: RuleContext) -> None:
    for node in ctx.document.select(("string",)):
        if H.is_fstring(node):
            ctx.report(node, "f-strings are forbidden")


def _check_wps306(ctx: RuleContext) -> None:
    for node in ctx.document.select(("class_definition",)):
        args = H.first_child_kind(ctx, node, "argument_list")
        if args and re.search(r"\bobject\b", args.text()):
            ctx.report(node, "Explicit object base class is forbidden")


def _check_wps307(ctx: RuleContext) -> None:
    for node in ctx.document.select(("list_comprehension",)):
        if node.text().count(" if ") > 1:
            ctx.report(node, "Multiple ifs in comprehension")


def _check_wps312(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        text = node.text()
        m = re.match(r"(.+?)\s*(==|!=|is|is not)\s*(.+)", text)
        if m and m.group(1).strip() == m.group(3).strip():
            ctx.report(node, "Comparison of variable to itself")


def _check_wps321(ctx: RuleContext) -> None:
    for node in ctx.document.select(("string",)):
        prefixes = ""
        i = 0
        text = node.text()
        while i < len(text) and text[i].isalpha():
            prefixes += text[i]
            i += 1
        if any(c.isupper() for c in prefixes):
            ctx.report(node, "Uppercase string modifier")


def _check_wps322(ctx: RuleContext) -> None:
    for node in ctx.document.select(("string",)):
        t = node.text().lstrip("frubFRUB")
        content = H.string_content(node)
        if (t.startswith('"""') or t.startswith("'''")) and "\n" not in content:
            ctx.report(node, "Triple quotes for singleline strings")


def _check_wps323(ctx: RuleContext) -> None:
    for node in ctx.document.select(("binary_operator",)):
        if " % " in node.text() and ("'" in node.text() or '"' in node.text()):
            ctx.report(node, "% string formatting is forbidden")


def _check_wps324(ctx: RuleContext) -> None:
    for node in ctx.document.select(("function_definition",)):
        returns = [n for n in H.walk_subtree(ctx, node) if n.kind == "return_statement"]
        bare = sum(1 for r in returns if r.text().strip() == "return")
        valued = len(returns) - bare
        if bare and valued:
            ctx.report(node, "Inconsistent return statements")


def _check_wps325(ctx: RuleContext) -> None:
    for node in ctx.document.select(("function_definition",)):
        yields = [n for n in H.walk_subtree(ctx, node) if n.kind in ("yield", "yield_statement")]
        texts = {y.text().strip() for y in yields}
        if any(t == "yield" for t in texts) and any(t != "yield" for t in texts):
            ctx.report(node, "Inconsistent yield statements")


def _check_wps326(ctx: RuleContext) -> None:
    for node in ctx.document.select(("concatenated_string",)):
        ctx.report(node, "Implicit string concatenation")


def _check_wps332(ctx: RuleContext) -> None:
    for node in ctx.document.select(("named_expression",)):
        ctx.report(node, "Walrus operator is forbidden")


def _check_wps336(ctx: RuleContext) -> None:
    for node in ctx.document.select(("binary_operator",)):
        kids = ctx.children(node)
        if " + " in node.text() and any(c.kind == "string" for c in kids):
            ctx.report(node, "Explicit string concatenation; prefer format")


def _check_wps344(ctx: RuleContext) -> None:
    for node in ctx.document.select(("binary_operator",)):
        text = node.text().replace(" ", "")
        if "/0" in text or "%0" in text or "//0" in text:
            ctx.report(node, "Division or modulo by zero")


def _check_wps347(ctx: RuleContext) -> None:
    for node in ctx.document.select(("import_from_statement",)):
        if " import *" in node.text() or node.text().rstrip().endswith("*"):
            ctx.report(node, "Star import is forbidden")


def _check_wps350(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        text = node.text()
        m = re.match(r"(\w+)\s*=\s*\1\s*([+\-*/%]|//|\*\*)", text)
        if m:
            ctx.report(node, "Use augmented assignment")


def _check_wps358(ctx: RuleContext) -> None:
    for node in ctx.document.select(("float",)):
        if node.text() in ("0.0", ".0", "0."):
            ctx.report(node, "Float zero is forbidden; use 0")


def _check_wps363(ctx: RuleContext) -> None:
    for node in ctx.document.select(("raise_statement",)):
        if "SystemExit" in node.text():
            ctx.report(node, "Raising SystemExit is forbidden")


def _check_wps364(ctx: RuleContext) -> None:
    for node in ctx.document.select(("unary_operator", "not_operator", "comparison_operator")):
        text = node.text()
        if re.search(r"\bnot\s+[^\s]+\s+in\b", text) and " not in " not in text:
            ctx.report(node, "Use 'a not in b' instead of 'not a in b'")


_EXPLICIT: dict[str, tuple] = {
    'WPS300': (_check_wps300, ()),
    'WPS301': (_check_wps301, ()),
    'WPS302': (_check_wps302, ()),
    'WPS303': (_check_wps303, ()),
    'WPS304': (_check_wps304, ()),
    'WPS305': (_check_wps305, ()),
    'WPS306': (_check_wps306, ()),
    'WPS307': (_check_wps307, ()),
    'WPS312': (_check_wps312, ()),
    'WPS321': (_check_wps321, ()),
    'WPS322': (_check_wps322, ()),
    'WPS323': (_check_wps323, ()),
    'WPS324': (_check_wps324, ()),
    'WPS325': (_check_wps325, ()),
    'WPS326': (_check_wps326, ()),
    'WPS332': (_check_wps332, ()),
    'WPS336': (_check_wps336, ()),
    'WPS344': (_check_wps344, ()),
    'WPS347': (_check_wps347, ()),
    'WPS350': (_check_wps350, ()),
    'WPS358': (_check_wps358, ()),
    'WPS363': (_check_wps363, ()),
    'WPS364': (_check_wps364, ()),
}


def register() -> list[Rule]:
    # Only register implemented checkers — planned stubs stay in catalog only.
    return [
        make_rule(code, MESSAGES[code], targets, checker)
        for code, (checker, targets) in _EXPLICIT.items()
    ]
