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


def _check_wps511(ctx: RuleContext) -> None:
    for node in ctx.document.select(("boolean_operator",)):
        if any(a.kind == "boolean_operator" for a in ctx.ancestors(node)):
            continue
        matches = re.findall(r"isinstance\s*\(\s*([^,]+?)\s*,", node.text())
        vars_seen: dict[str, int] = {}
        for raw in matches:
            key = raw.strip()
            vars_seen[key] = vars_seen.get(key, 0) + 1
        if any(count >= 2 for count in vars_seen.values()):
            ctx.report(node, MESSAGES["WPS511"])


def _check_wps512(ctx: RuleContext) -> None:
    for node in ctx.document.select(("call",)):
        if resolve_call_name(ctx.document, node) != "isinstance":
            continue
        args = H.first_child_kind(ctx, node, "argument_list")
        if args is None:
            continue
        positional = [
            c
            for c in ctx.children(args)
            if c.kind not in ("(", ")", ",") and not c.text().strip().startswith("*")
        ]
        # Skip keyword args like `bar=(1,)` — only the types positional arg.
        types_arg = None
        pos_idx = 0
        for child in positional:
            if "=" in child.text() and not child.text().strip().startswith("="):
                continue  # keyword argument
            pos_idx += 1
            if pos_idx == 2:
                types_arg = child
                break
        if types_arg is None or types_arg.kind != "tuple":
            continue
        elems = [
            c for c in ctx.children(types_arg) if c.kind not in ("(", ")", ",")
        ]
        if len(elems) == 1:
            ctx.report(node, MESSAGES["WPS512"])


def _check_wps513(ctx: RuleContext) -> None:
    for else_node in ctx.document.select(("else_clause",)):
        # Only if/else — skip try/for/while else clauses.
        parent = next(
            (
                a
                for a in ctx.ancestors(else_node)
                if a.kind
                in ("if_statement", "try_statement", "for_statement", "while_statement")
            ),
            None,
        )
        if parent is None or parent.kind != "if_statement":
            continue
        block = H.first_child_kind(ctx, else_node, "block")
        if block is None:
            continue
        stmts = [
            c
            for c in ctx.children(block)
            if c.kind not in ("comment",) and len(getattr(c, "kind", "") or "") > 1
        ]
        if len(stmts) == 1 and stmts[0].kind == "if_statement":
            ctx.report(else_node, MESSAGES["WPS513"])


def _check_wps514(ctx: RuleContext) -> None:
    for node in ctx.document.select(("boolean_operator",)):
        if any(a.kind == "boolean_operator" for a in ctx.ancestors(node)):
            continue
        if " or " not in f" {node.text()} ":
            continue
        matches = re.findall(r"(?<![\w.])([\w.]+)\s*==\s*", node.text())
        vars_seen: dict[str, int] = {}
        for key in matches:
            vars_seen[key] = vars_seen.get(key, 0) + 1
        if any(count >= 2 for count in vars_seen.values()):
            ctx.report(node, MESSAGES["WPS514"])


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


def _check_wps517(ctx: RuleContext) -> None:
    for node in ctx.document.select(("list_splat",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("*",)]
        if kids and kids[0].kind in ("list", "tuple", "set"):
            ctx.report(node, MESSAGES["WPS517"])


def _check_wps518(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement",)):
        if re.search(r"for\s+\w+\s+in\s+range\(\s*len\(", node.text()):
            ctx.report(node, "Implicit enumerate(); use enumerate()")


def _check_wps519(ctx: RuleContext) -> None:
    zero_assigns: dict[str, object] = {}
    for node in ctx.document.select(("assignment",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("=",)]
        if (
            len(kids) >= 2
            and kids[0].kind == "identifier"
            and kids[-1].kind == "integer"
            and kids[-1].text() == "0"
        ):
            zero_assigns[kids[0].text()] = node
    for node in ctx.document.select(("for_statement",)):
        block = H.first_child_kind(ctx, node, "block")
        if block is None:
            continue
        stmts = [
            c
            for c in ctx.children(block)
            if len(getattr(c, "kind", "") or "") > 1 and c.kind != "comment"
        ]
        if len(stmts) != 1 or stmts[0].kind != "expression_statement":
            continue
        aug = H.first_child_kind(ctx, stmts[0], "augmented_assignment")
        if aug is None:
            continue
        aug_kids = [c for c in ctx.children(aug) if c.kind not in ("+=",)]
        if not aug_kids or aug_kids[0].kind != "identifier":
            continue
        if "+=" not in aug.text():
            continue
        name = aug_kids[0].text()
        if name in zero_assigns:
            ctx.report(node, MESSAGES["WPS519"])


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


def _check_wps522(ctx: RuleContext) -> None:
    primitive = re.compile(
        r"^lambda\s*:\s*(\[\s*\]|\{\s*\}|\(\s*\)|set\(\s*\)|0|0\.0|False|True|None|\"\"|\'\')\s*$"
    )
    for node in ctx.document.select(("lambda",)):
        if primitive.match(node.text().strip()):
            ctx.report(node, MESSAGES["WPS522"])


def _check_wps523(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        if re.match(r"\w+\s*,\s*\w+\s*=\s*\w+\s*,\s*\w+", node.text()):
            ctx.report(node, MESSAGES['WPS523'])


def _check_wps524(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("=",)]
        if len(kids) < 2:
            continue
        left, right = kids[0], kids[-1]
        if left.kind == "attribute" and right.kind == "attribute" and left.text() == right.text():
            ctx.report(node, MESSAGES["WPS524"])


def _check_wps525(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        if not re.search(r"\bin\b", node.text()):
            continue
        for child in ctx.children(node):
            if child.kind not in ("list", "tuple", "set"):
                continue
            elems = [
                c
                for c in ctx.children(child)
                if c.kind not in ("[", "]", "(", ")", "{", "}", ",")
            ]
            if len(elems) == 1:
                ctx.report(node, MESSAGES["WPS525"])
                break


def _check_wps526(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement",)):
        loop_var = None
        for child in ctx.children(node):
            if child.kind == "identifier":
                loop_var = child.text()
                break
        if loop_var is None:
            continue
        block = H.first_child_kind(ctx, node, "block")
        if block is None:
            continue
        stmts = [
            c
            for c in ctx.children(block)
            if len(getattr(c, "kind", "") or "") > 1 and c.kind != "comment"
        ]
        if len(stmts) != 1 or stmts[0].kind != "expression_statement":
            continue
        yield_node = H.first_child_kind(ctx, stmts[0], "yield")
        if yield_node is None:
            continue
        # `yield x` where x is the loop variable — prefer `yield from`
        if re.fullmatch(rf"yield\s+{re.escape(loop_var)}", yield_node.text().strip()):
            ctx.report(node, MESSAGES["WPS526"])


def _check_wps528(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("for", "in", ":", "async")]
        # for k in d: ... — identifiers for target and iterable
        idents = [c for c in kids if c.kind == "identifier"]
        if len(idents) < 2:
            continue
        loop_var, iterable = idents[0].text(), idents[1].text()
        block = H.first_child_kind(ctx, node, "block")
        if block is None:
            continue
        pattern = re.compile(rf"\b{re.escape(iterable)}\s*\[\s*{re.escape(loop_var)}\s*\]")
        if pattern.search(block.text()):
            ctx.report(node, MESSAGES["WPS528"])


def _check_wps529(ctx: RuleContext) -> None:
    for node in ctx.document.select(("conditional_expression",)):
        # d[k] if k in d else default
        if re.search(
            r"(\w+)\s*\[\s*(\w+)\s*\]\s+if\s+\2\s+in\s+\1\s+else\b",
            node.text(),
        ):
            ctx.report(node, MESSAGES["WPS529"])


def _check_wps530(ctx: RuleContext) -> None:
    for node in ctx.document.select(("subscript",)):
        if re.search(r"(\w+)\s*\[\s*len\s*\(\s*\1\s*\)\s*-\s*\d+\s*\]", node.text()):
            ctx.report(node, MESSAGES["WPS530"])


def _check_wps531(ctx: RuleContext) -> None:
    for node in ctx.document.select(("if_statement",)):
        text = node.text()
        if "return True" in text and "return False" in text:
            ctx.report(node, "If that simply returns booleans")


def _check_wps532(ctx: RuleContext) -> None:
    # Identity checks with non-singleton literals (numbers / empty containers).
    # Skips None/True/False/strings (covered by WPS521).
    for node in ctx.document.select(("comparison_operator",)):
        text = node.text()
        if not re.search(r"\bis\b", text):
            continue
        if re.search(r"\bis\s+(not\s+)?(\d+(\.\d+)?|\[\s*\]|\{\s*\}|\(\s*\))", text):
            ctx.report(node, MESSAGES["WPS532"])


def _check_wps533(ctx: RuleContext) -> None:
    def _condition_text(stmt) -> str | None:
        # First meaningful child after if/elif keyword.
        skip = {"if", "elif", ":", "else", "else_clause", "elif_clause", "block", "comment"}
        for child in ctx.children(stmt):
            if child.kind in skip:
                continue
            if len(getattr(child, "kind", "") or "") <= 1 and child.kind not in (
                "identifier",
                "true",
                "false",
                "none",
            ):
                continue
            if child.kind in ("else_clause", "elif_clause", "block"):
                continue
            return child.text().strip()
        return None

    for node in ctx.document.select(("if_statement",)):
        conds: list[str] = []
        main = _condition_text(node)
        if main is not None:
            conds.append(main)
        for child in ctx.children(node):
            if child.kind == "elif_clause":
                c = _condition_text(child)
                if c is not None:
                    conds.append(c)
        if len(conds) != len(set(conds)):
            ctx.report(node, MESSAGES["WPS533"])


def _check_wps534(ctx: RuleContext) -> None:
    for node in ctx.document.select(("conditional_expression",)):
        text = node.text().strip()
        if re.search(r"\bif\s+(True|False)\s+else\b", text):
            ctx.report(node, MESSAGES["WPS534"])
            continue
        # same value on both branches: `a if cond else a`
        m = re.match(r"^(.+?)\s+if\s+.+\s+else\s+(.+)$", text, re.DOTALL)
        if m and m.group(1).strip() == m.group(2).strip():
            ctx.report(node, MESSAGES["WPS534"])


def _check_wps535(ctx: RuleContext) -> None:
    for node in ctx.document.select(("match_statement",)):
        cases = [n.text() for n in H.walk_subtree(ctx, node) if n.kind == "case_clause"]
        if len(cases) != len(set(cases)):
            ctx.report(node, MESSAGES['WPS535'])


def _check_wps536(ctx: RuleContext) -> None:
    for node in ctx.document.select(("match_statement",)):
        for child in ctx.children(node):
            if child.kind in ("list", "set", "dictionary"):
                ctx.report(node, MESSAGES["WPS536"])
                break


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
    'WPS511': (_check_wps511, ()),
    'WPS512': (_check_wps512, ()),
    'WPS513': (_check_wps513, ()),
    'WPS514': (_check_wps514, ()),
    'WPS515': (_check_wps515, ("call",)),
    'WPS516': (_check_wps516, ()),
    'WPS517': (_check_wps517, ()),
    'WPS518': (_check_wps518, ()),
    'WPS519': (_check_wps519, ()),
    'WPS520': (_check_wps520, ()),
    'WPS521': (_check_wps521, ()),
    'WPS522': (_check_wps522, ()),
    'WPS523': (_check_wps523, ()),
    'WPS524': (_check_wps524, ()),
    'WPS525': (_check_wps525, ()),
    'WPS526': (_check_wps526, ()),
    'WPS528': (_check_wps528, ()),
    'WPS529': (_check_wps529, ()),
    'WPS530': (_check_wps530, ()),
    'WPS531': (_check_wps531, ()),
    'WPS532': (_check_wps532, ()),
    'WPS533': (_check_wps533, ()),
    'WPS534': (_check_wps534, ()),
    'WPS535': (_check_wps535, ()),
    'WPS536': (_check_wps536, ()),
}


def register() -> list[Rule]:
    # Only register implemented/partial checkers — planned stubs stay in catalog only.
    return [
        make_rule(code, MESSAGES[code], targets, checker)
        for code, (checker, targets) in _EXPLICIT.items()
    ]
