"""WPS OOP rules (WPS6xx)."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, resolve_call_name
from plintus.rules.wps._factory import make_rule
from plintus.rules.wps import helpers as H
from plintus.rules.wps.catalog_data import MESSAGES


def _check_wps600(ctx: RuleContext) -> None:
    forbid = {
        "int",
        "str",
        "bool",
        "float",
        "bytes",
        "complex",
        "list",
        "dict",
        "set",
        "tuple",
        "frozenset",
    }
    for node in ctx.nodes:
        args = H.first_child_kind(ctx, node, "argument_list")
        if args is None:
            continue
        for child in ctx.children(args):
            if child.kind == "identifier" and child.text() in forbid:
                # allow if Enum in bases
                if "Enum" in node.text().split(":", 1)[0]:
                    continue
                ctx.report(child, f"Subclassing builtin is forbidden: {child.text()}")


def _check_wps601(ctx: RuleContext) -> None:
    for cls in ctx.nodes:
        block = H.first_child_kind(ctx, cls, "block")
        if block is None:
            continue
        class_attrs = set()
        for child in ctx.children(block):
            assign = child if child.kind == "assignment" else H.first_child_kind(ctx, child, "assignment")
            if assign is None:
                continue
            for c in ctx.children(assign):
                if c.kind == "identifier":
                    class_attrs.add(c.text())
                    break
        for assign in [n for n in H.walk_subtree(ctx, cls) if n.kind == "assignment"]:
            text = assign.text()
            if text.startswith("self."):
                name = text.split("=", 1)[0].strip()[5:]
                if name in class_attrs:
                    ctx.report(assign, f"Instance attribute shadows class attribute: {name}")


def _decorator_is_staticmethod(ctx: RuleContext, node) -> bool:
    """True for ``@staticmethod`` / ``@foo.staticmethod`` (exact name), not wrappers."""
    for child in ctx.children(node):
        if child.kind == "identifier":
            return child.text() == "staticmethod"
        if child.kind == "attribute":
            idents = [c for c in ctx.children(child) if c.kind == "identifier"]
            return bool(idents) and idents[-1].text() == "staticmethod"
        if child.kind == "call":
            callees = [c for c in ctx.children(child) if c.kind in ("identifier", "attribute")]
            if not callees:
                return False
            callee = callees[0]
            if callee.kind == "identifier":
                return callee.text() == "staticmethod"
            idents = [c for c in ctx.children(callee) if c.kind == "identifier"]
            return bool(idents) and idents[-1].text() == "staticmethod"
    return False


def _check_wps602(ctx: RuleContext) -> None:
    for node in ctx.document.select(("decorator",)):
        if _decorator_is_staticmethod(ctx, node):
            ctx.report(node, "@staticmethod is forbidden")


def _check_wps603(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = H.def_name(ctx, node)
        if name in H.MAGIC_METHODS_BLACKLIST:
            ctx.report(node, f"Forbidden magic method: {name}")


def _check_wps604(ctx: RuleContext) -> None:
    allowed = H.FUNCTION_KINDS | {"assignment", "expression_statement", "decorated_definition", "class_definition", "pass_statement", "type_alias_statement"}
    for cls in ctx.nodes:
        block = H.first_child_kind(ctx, cls, "block")
        if block is None:
            continue
        for child in ctx.children(block):
            if child.kind in ("comment",):
                continue
            if len(child.kind) <= 1:
                continue
            if child.kind not in allowed and child.kind not in ("function_definition",):
                if child.kind in ("for_statement", "while_statement", "if_statement", "with_statement", "try_statement"):
                    ctx.report(child, "Incorrect node inside class body")


def _check_wps605(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        if H.enclosing_class(ctx, node) is None:
            continue
        # skip staticmethod
        parent = ctx.parent(node)
        if parent is not None and parent.kind == "decorated_definition":
            if any("staticmethod" in d.text() for d in ctx.children(parent) if d.kind == "decorator"):
                continue
        if H.countable_param_count(ctx, node) == 0 and len(H.param_names(ctx, node)) == 0:
            ctx.report(node, "Method without arguments")


def _check_wps606(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        args = H.first_child_kind(ctx, node, "argument_list")
        if args is None:
            continue
        for child in ctx.children(args):
            if child.kind in ("(", ")", ",", "keyword_argument"):
                continue
            if child.kind in ("call", "binary_operator", "parenthesized_expression", "lambda"):
                ctx.report(child, "Base class must be a class-like name")


def _check_wps607(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("=",)]
        if not kids:
            continue
        left = kids[0]
        if left.kind == "identifier" and left.text() == "__slots__":
            right = kids[-1] if len(kids) > 1 else None
            if right is not None and right.kind == "list":
                ctx.report(node, "__slots__ must not be a list")
            if right is not None and right.kind == "tuple":
                seen = set()
                for c in H.walk_subtree(ctx, right):
                    if c.kind == "string":
                        val = H.string_content(c)
                        if val in seen:
                            ctx.report(c, "Duplicate __slots__ entry")
                        seen.add(val)


def _check_wps608(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = resolve_call_name(ctx.document, node)
        if name != "super":
            continue
        args = H.first_child_kind(ctx, node, "argument_list")
        has_args = False
        if args is not None:
            pos = [c for c in ctx.children(args) if c.kind not in ("(", ")", ",")]
            has_args = bool(pos)
        if has_args:
            ctx.report(node, "super() must be called without arguments")
        if H.enclosing_function(ctx, node) is None:
            ctx.report(node, "super() outside of a method")


def _check_wps609(ctx: RuleContext) -> None:
    banned = {"__str__", "__repr__", "__delitem__", "__truediv__", "__add__", "__eq__"}
    for node in ctx.nodes:
        if node.kind != "call":
            continue
        # attr call like foo.__str__()
        kids = ctx.children(node)
        if not kids:
            continue
        func = kids[0]
        if func.kind == "attribute":
            idents = [c for c in ctx.children(func) if c.kind == "identifier"]
            if idents and idents[-1].text() in banned:
                base = idents[0].text() if idents else ""
                if base not in ("self", "cls", "super"):
                    ctx.report(node, f"Direct magic attribute access: {idents[-1].text()}")


def _check_wps610(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        if not H.is_async_function(ctx, node):
            continue
        name = H.def_name(ctx, node)
        if name in H.ASYNC_MAGIC_METHODS_BLACKLIST:
            ctx.report(node, f"Async magic method is forbidden: {name}")


def _check_wps611(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = H.def_name(ctx, node)
        if name not in H.YIELD_MAGIC_METHODS_BLACKLIST:
            continue
        if H.count_kind_in_subtree(ctx, node, "yield") or H.count_kind_in_subtree(ctx, node, "yield_statement"):
            ctx.report(node, f"Yield inside magic method: {name}")


def _check_wps612(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        body = H.function_body(ctx, node)
        if body is None:
            continue
        stmts = [c for c in ctx.children(body) if len(c.kind) > 1]
        if len(stmts) != 1:
            continue
        text = stmts[0].text().strip()
        name = H.def_name(ctx, node)
        if name and text.startswith("return super().") and name in text:
            ctx.report(node, "Useless overwritten method")


def _check_wps613(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = resolve_call_name(ctx.document, node)
        if name != "super":
            continue
        parent = ctx.parent(node)
        if parent is None or parent.kind != "attribute":
            continue
        idents = [c for c in ctx.children(parent) if c.kind == "identifier"]
        if not idents:
            continue
        accessed = idents[-1].text()
        func = H.enclosing_function(ctx, node)
        if func is None:
            continue
        fname = H.def_name(ctx, func)
        if fname and accessed != fname:
            ctx.report(parent, f"super() accesses incorrect method: {accessed}")


def _check_wps614(ctx: RuleContext) -> None:
    markers = ("property", "classmethod", "staticmethod")
    for node in ctx.document.select(("decorator",)):
        if not any(m in node.text() for m in markers):
            continue
        # find function
        parent = ctx.parent(node)
        if parent is None or parent.kind != "decorated_definition":
            continue
        func = None
        for c in ctx.children(parent):
            if c.kind in H.FUNCTION_KINDS:
                func = c
                break
        if func is not None and H.enclosing_class(ctx, parent) is None:
            ctx.report(node, "Descriptor decorator on a regular function")


def _check_wps615(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = H.def_name(ctx, node)
        if name and (name.startswith("get_") or name.startswith("set_")):
            if H.enclosing_class(ctx, node) is not None:
                ctx.report(node, f"Unpythonic getter/setter: {name}")


def _check_wps616(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = resolve_call_name(ctx.document, node)
        if name != "super":
            continue
        args = H.first_child_kind(ctx, node, "argument_list")
        if args is not None:
            pos = [c for c in ctx.children(args) if c.kind not in ("(", ")", ",")]
            if pos:
                continue
        # inside comprehension?
        if any(a.kind in ("list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression") for a in ctx.ancestors(node)):
            ctx.report(node, "Bare super() in buggy comprehension context")


def _check_wps617(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        text = node.text()
        if "self." in text.split("=", 1)[0] and "lambda" in text:
            ctx.report(node, "Lambda assigned as attribute")


_CHECKS = {
    'WPS600': (_check_wps600, ("class_definition",)),
    'WPS601': (_check_wps601, ("class_definition",)),
    'WPS602': (_check_wps602, ()),
    'WPS603': (_check_wps603, ("function_definition",)),
    'WPS604': (_check_wps604, ("class_definition",)),
    'WPS605': (_check_wps605, ("function_definition",)),
    'WPS606': (_check_wps606, ("class_definition",)),
    'WPS607': (_check_wps607, ()),
    'WPS608': (_check_wps608, ("call",)),
    'WPS609': (_check_wps609, ("call",)),
    'WPS610': (_check_wps610, ("function_definition",)),
    'WPS611': (_check_wps611, ("function_definition",)),
    'WPS612': (_check_wps612, ("function_definition",)),
    'WPS613': (_check_wps613, ("call",)),
    'WPS614': (_check_wps614, ()),
    'WPS615': (_check_wps615, ("function_definition",)),
    'WPS616': (_check_wps616, ("call",)),
    'WPS617': (_check_wps617, ()),
}


def register() -> list[Rule]:
    return [make_rule(code, MESSAGES[code], targets, checker) for code, (checker, targets) in _CHECKS.items()]
