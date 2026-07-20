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


_COMPARE_OPS = ("==", "!=", "<=", ">=", "<", ">", "is not", "is", "not in", "in")


def _split_comparison(text: str) -> tuple[str, str, str] | None:
    for op in _COMPARE_OPS:
        parts = re.split(rf"\s*{re.escape(op)}\s*", text, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), op, parts[1].strip()
    return None


def _check_wps308(ctx: RuleContext) -> None:
    lit = re.compile(
        r"^(True|False|None|-?\d+(\.\d+)?([eE][+-]?\d+)?|"
        r"0[xXoObB][\da-fA-F_]+|"
        r"['\"][^'\"]*['\"]|"
        r"\[\s*\]|\{\s*\}|\(\s*\))$"
    )
    for node in ctx.document.select(("comparison_operator",)):
        split = _split_comparison(node.text())
        if not split:
            continue
        left, op, right = split
        if op in ("in", "not in"):
            continue
        if lit.match(left) and lit.match(right):
            ctx.report(node, "Comparing two literals")


def _check_wps309(ctx: RuleContext) -> None:
    # Argument first: allow `x == 1` / `x > 3`; forbid Yoda `1 == x` / `3 < x`.
    lit_pat = re.compile(
        r"^(True|False|None|-?\d+(\.\d+)?([eE][+-]?\d+)?|"
        r"0[xXoObB][\da-fA-F_]+|"
        r"['\"].*['\"])$"
    )
    for node in ctx.document.select(("comparison_operator",)):
        split = _split_comparison(node.text())
        if not split:
            continue
        left, op, right = split
        if op in ("in", "not in", "is", "is not"):
            continue
        if lit_pat.match(left) and not lit_pat.match(right):
            ctx.report(node, "Argument should come first in comparison")


def _check_wps310(ctx: RuleContext) -> None:
    for node in ctx.document.select(("integer", "float")):
        text = node.text()
        if re.search(r"0[XOB]", text) or re.search(r"[0-9.]E", text):
            ctx.report(node, "Uppercase number base/exponent is forbidden")


def _check_wps311(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        # Strip string literals so `'in' in x` does not count as two memberships.
        text = re.sub(r"('''|\"\"\"|'|\").*?\1", '""', node.text(), flags=re.S)
        # Count membership operators (treat `not in` as one).
        text = re.sub(r"\bnot\s+in\b", " in ", text)
        if len(re.findall(r"\bin\b", text)) >= 2:
            ctx.report(node, "Multiple in checks in one comparison")


def _check_wps312(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        text = node.text()
        m = re.match(r"(.+?)\s*(==|!=|is|is not)\s*(.+)", text)
        if m and m.group(1).strip() == m.group(3).strip():
            ctx.report(node, "Comparison of variable to itself")


def _check_wps315(ctx: RuleContext) -> None:
    for node in ctx.document.select(("class_definition",)):
        args = H.first_child_kind(ctx, node, "argument_list")
        if not args:
            continue
        bases = [
            c
            for c in ctx.children(args)
            if c.kind not in ("(", ")", ",") and c.text().strip() not in ("(", ")", ",")
        ]
        texts = [b.text().strip() for b in bases]
        if "object" in texts and len(texts) > 1:
            ctx.report(node, "Extra object in parent class list")


def _check_wps316(ctx: RuleContext) -> None:
    for node in ctx.document.select(("with_statement",)):
        if re.search(r" as\s*[\(\[]", node.text()):
            ctx.report(node, "Multiple assignment targets for context manager")


def _check_wps327(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement", "while_statement")):
        body = H.first_child_kind(ctx, node, "block")
        if body is None:
            continue
        stmts = [
            c
            for c in ctx.children(body)
            if c.kind not in ("comment",) and not (c.kind == "expression_statement" and not c.text().strip())
        ]
        # Last non-comment statement is continue.
        meaningful = [c for c in stmts if c.kind != "comment"]
        if meaningful and meaningful[-1].kind == "continue_statement":
            ctx.report(meaningful[-1], "Meaningless continue in loop")


def _check_wps339(ctx: RuleContext) -> None:
    for node in ctx.document.select(("integer",)):
        text = node.text().replace("_", "")
        # Leading zeros in decimal, or redundant zeros in bases: 00, 0x00, 0b00, 0o00
        if re.fullmatch(r"0\d+", text):
            ctx.report(node, "Meaningless zeros in number")
        elif re.fullmatch(r"0[xXoObB]0+[0-9a-fA-F]*", text) and not re.fullmatch(
            r"0[xXoObB]0", text
        ):
            # 0x0 is a single zero — still meaningless per wemake; flag multi-zero padding
            if re.search(r"0[xXoObB]0{2,}", text) or re.fullmatch(r"0[xXoObB]0+", text):
                ctx.report(node, "Meaningless zeros in number")


def _check_wps340(ctx: RuleContext) -> None:
    for node in ctx.document.select(("float", "integer")):
        if re.search(r"[eE]\+\d", node.text()):
            ctx.report(node, "Extra + in exponent is forbidden")


def _check_wps341(ctx: RuleContext) -> None:
    for node in ctx.document.select(("integer",)):
        text = node.text()
        m = re.match(r"0[xX]([0-9a-fA-F_]+)$", text)
        if not m:
            continue
        hex_part = m.group(1).replace("_", "")
        # Hex made only of letters a-f (looks like a word).
        if hex_part and re.fullmatch(r"[a-fA-F]+", hex_part):
            ctx.report(node, "Letters as hex numbers are forbidden")


def _check_wps343(ctx: RuleContext) -> None:
    for node in ctx.document.select(("integer", "float")):
        if node.text().rstrip().endswith("J"):
            ctx.report(node, "Uppercase complex suffix is forbidden")


def _check_wps345(ctx: RuleContext) -> None:
    identity = re.compile(
        r"^(?:(\w+)\*(1)|(1)\*(\w+)|(\w+)\+(0)|(0)\+(\w+)|(\w+)-(0)|"
        r"(\w+)/(1)|(\w+)//(1)|(\w+)\*\*(1)|(\w+)%(1))$"
    )
    for node in ctx.document.select(("binary_operator",)):
        text = node.text().replace(" ", "")
        if identity.match(text):
            ctx.report(node, "Meaningless math with 0 or 1")


def _check_wps346(ctx: RuleContext) -> None:
    for node in ctx.document.select(("unary_operator", "binary_operator")):
        compact = node.text().replace(" ", "")
        if "--" in compact or compact.startswith("-(-"):
            ctx.report(node, "Double minus is forbidden")


def _check_wps348(ctx: RuleContext) -> None:
    for i, line in enumerate(ctx.source.splitlines()):
        stripped = line.lstrip()
        if not stripped.startswith(".") or stripped.startswith("..."):
            continue
        reported = False
        for node in ctx.document.select(("attribute",)):
            if node.line == i + 1:
                ctx.report(node, "Line must not start with a dot")
                reported = True
                break
        if not reported:
            roots = ctx.document.select(("module",))
            if roots:
                ctx.report(roots[0], "Line must not start with a dot")


def _check_wps351(ctx: RuleContext) -> None:
    empty_lits = ("[]", "{}", "()", "''", '""', "set()")
    for node in ctx.document.select(("if_statement", "while_statement", "elif_clause")):
        text = node.text()
        # `if []:` / `while '':`
        m = re.match(r"(?:if|while|elif)\s+(.+?)\s*:", text.split("\n", 1)[0])
        if not m:
            continue
        cond = m.group(1).strip()
        if cond in empty_lits or cond in ("True", "False", "None"):
            # True/False/None in if are more WPS502; only flag empty literals here.
            if cond in empty_lits:
                ctx.report(node, "Unnecessary literal in condition")


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
    'WPS308': (_check_wps308, ()),
    'WPS309': (_check_wps309, ()),
    'WPS310': (_check_wps310, ()),
    'WPS311': (_check_wps311, ()),
    'WPS312': (_check_wps312, ()),
    'WPS315': (_check_wps315, ()),
    'WPS316': (_check_wps316, ()),
    'WPS321': (_check_wps321, ()),
    'WPS322': (_check_wps322, ()),
    'WPS323': (_check_wps323, ()),
    'WPS324': (_check_wps324, ()),
    'WPS325': (_check_wps325, ()),
    'WPS326': (_check_wps326, ()),
    'WPS327': (_check_wps327, ()),
    'WPS332': (_check_wps332, ()),
    'WPS336': (_check_wps336, ()),
    'WPS339': (_check_wps339, ()),
    'WPS340': (_check_wps340, ()),
    'WPS341': (_check_wps341, ()),
    'WPS343': (_check_wps343, ()),
    'WPS344': (_check_wps344, ()),
    'WPS345': (_check_wps345, ()),
    'WPS346': (_check_wps346, ()),
    'WPS347': (_check_wps347, ()),
    'WPS348': (_check_wps348, ()),
    'WPS350': (_check_wps350, ()),
    'WPS351': (_check_wps351, ()),
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
