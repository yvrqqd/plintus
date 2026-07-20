"""CLS001–CLS002 — class method order and blank lines (WPS338 + PEP8)."""

from __future__ import annotations

import re

from plintus.api import Fix, Rule, RuleContext, Severity
from plintus.rules.cbp_helpers import function_name, utf8_slice

_METHOD_KINDS = frozenset({"function_definition", "decorated_definition"})

# Newspaper order (WPS338): higher = earlier in class.
_SPECIAL_METHOD_PRIORITY = {
    "__init_subclass__": 7,
    "__new__": 6,
    "__init__": 5,
    "__call__": 4,
    "__await__": 3,
}
_PUBLIC_AND_MAGIC = 2
_PROTECTED = 1
_PRIVATE = 0

_UNUSED_NAME = re.compile(r"^_+$")


class ClassMethodOrder(Rule):
    """CLS001: WPS338 newspaper order of methods inside a class (+ safe autofix)."""

    id = "CLS001"
    message = (
        "Class methods must follow newspaper order: "
        "__init_subclass__/__new__/__init__/__call__/__await__, "
        "then public/magic, protected, private"
    )
    severity = Severity.ERROR
    targets = ("class_definition",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            block = _class_block(ctx, node)
            if block is None:
                continue
            methods = _direct_methods(ctx, block)
            if len(methods) < 2:
                continue
            ordered = sorted(methods, key=lambda m: _method_priority(_method_name(ctx, m)), reverse=True)
            if [m.id for m in methods] == [m.id for m in ordered]:
                continue
            fix = _reorder_methods_fix(ctx, methods, ordered)
            ctx.report(node, fix=fix)


class ClassMethodBlankLines(Rule):
    """CLS002: exactly one blank line between adjacent methods in a class."""

    id = "CLS002"
    message = "Adjacent class methods must be separated by exactly one blank line"
    severity = Severity.WARNING
    targets = ("class_definition",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            block = _class_block(ctx, node)
            if block is None:
                continue
            kids = list(ctx.children(block))
            for prev, curr in zip(kids, kids[1:]):
                if prev.kind not in _METHOD_KINDS or curr.kind not in _METHOD_KINDS:
                    continue
                gap = utf8_slice(ctx.source, prev.end, curr.start)
                indent = _trailing_indent(gap)
                core = gap[: len(gap) - len(indent)] if indent else gap
                if core == "\n\n":
                    continue
                replacement = "\n\n" + indent
                ctx.report(
                    curr,
                    fix=Fix(
                        start=prev.end,
                        end=curr.start,
                        replacement=replacement,
                        safety="safe",
                    ),
                )


def _class_block(ctx: RuleContext, class_node):
    for child in ctx.children(class_node):
        if child.kind == "block":
            return child
    return None


def _direct_methods(ctx: RuleContext, block) -> list:
    return [c for c in ctx.children(block) if c.kind in _METHOD_KINDS]


def _method_name(ctx: RuleContext, node) -> str:
    if node.kind == "function_definition":
        return function_name(ctx, node) or ""
    if node.kind == "decorated_definition":
        for child in ctx.children(node):
            if child.kind == "function_definition":
                return function_name(ctx, child) or ""
    return ""


def _is_magic(name: str) -> bool:
    return name.startswith("__") and name.endswith("__") and len(name) > 4


def _is_private(name: str) -> bool:
    return name.startswith("__") and not _is_magic(name)


def _is_protected(name: str) -> bool:
    if not name.startswith("_") or _UNUSED_NAME.match(name):
        return False
    return not _is_private(name) and not _is_magic(name)


def _method_priority(name: str) -> int:
    if name in _SPECIAL_METHOD_PRIORITY:
        return _SPECIAL_METHOD_PRIORITY[name]
    if _is_protected(name):
        return _PROTECTED
    if _is_private(name):
        return _PRIVATE
    return _PUBLIC_AND_MAGIC


def _reorder_methods_fix(ctx: RuleContext, current: list, ordered: list) -> Fix:
    """Rewrite from first method to last, filling method slots in sorted order."""
    start = current[0].start
    end = current[-1].end
    ordered_texts = [m.text() for m in ordered]
    slot = 0
    parts: list[str] = []
    prev_end = start
    # Walk body children spanning first..last method
    block = ctx.parent(current[0])
    assert block is not None
    in_span = False
    for child in ctx.children(block):
        if child.id == current[0].id:
            in_span = True
        if not in_span:
            continue
        parts.append(utf8_slice(ctx.source, prev_end, child.start))
        if child.kind in _METHOD_KINDS:
            parts.append(ordered_texts[slot])
            slot += 1
        else:
            parts.append(child.text())
        prev_end = child.end
        if child.id == current[-1].id:
            break
    return Fix(start=start, end=end, replacement="".join(parts), safety="safe")


def _trailing_indent(gap: str) -> str:
    i = len(gap)
    while i > 0 and gap[i - 1] in " \t":
        i -= 1
    return gap[i:]
