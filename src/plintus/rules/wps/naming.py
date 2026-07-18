"""WPS naming rules (WPS1xx)."""

from __future__ import annotations

import keyword
import re

from plintus.api import Rule, RuleContext
from plintus.rules.wps._factory import make_rule
from plintus.rules.wps import helpers as H
from plintus.rules.wps.catalog_data import MESSAGES


def _iter_defined_names(ctx: RuleContext):
    """Yield (node, name) for definitions and assignments best-effort."""
    for kind in (
        "function_definition",
        "class_definition",
    ):
        for node in ctx.document.select((kind,)):
            name = H.def_name(ctx, node)
            if name:
                yield node, name
    for node in ctx.document.select(("assignment",)):
        for child in ctx.children(node):
            if child.kind == "identifier":
                yield child, child.text()
                break
            if child.kind in ("pattern_list", "tuple_pattern", "list_pattern", "tuple", "list"):
                for c in H.walk_subtree(ctx, child):
                    if c.kind == "identifier":
                        yield c, c.text()
                break
    for node in ctx.document.select(("parameters",)):
        for child in ctx.children(node):
            if child.kind == "identifier":
                yield child, child.text()
            elif child.kind in (
                "default_parameter",
                "typed_parameter",
                "typed_default_parameter",
            ):
                for c in ctx.children(child):
                    if c.kind == "identifier":
                        yield c, c.text()
                        break


def _check_wps100(ctx: RuleContext) -> None:
    stem = H.module_stem(ctx.path)
    if stem in H.MODULE_NAMES_BLACKLIST:
        roots = ctx.document.select(("module",))
        node = roots[0] if roots else None
        if node is not None:
            ctx.report(node, f"Blacklisted module name: {stem}")


def _check_wps101(ctx: RuleContext) -> None:
    stem = H.module_stem(ctx.path)
    if stem.startswith("__") and stem.endswith("__") and stem not in H.MAGIC_MODULE_NAMES_WHITELIST:
        roots = ctx.document.select(("module",))
        node = roots[0] if roots else None
        if node is not None:
            ctx.report(node, f"Magic module name is not allowed: {stem}")


def _check_wps102(ctx: RuleContext) -> None:
    stem = H.module_stem(ctx.path)
    if stem in H.MAGIC_MODULE_NAMES_WHITELIST:
        return
    if not H.MODULE_NAME_PATTERN.match(stem):
        roots = ctx.document.select(("module",))
        node = roots[0] if roots else None
        if node is not None:
            ctx.report(node, f"Module name does not match pattern: {stem}")


def _check_wps110(ctx: RuleContext) -> None:
    allowed = set(H.cfg_list(ctx, "allowed_domain_names"))
    forbidden = set(H.cfg_list(ctx, "forbidden_domain_names"))
    blacklist = (H.VARIABLE_NAMES_BLACKLIST | forbidden) - allowed
    for node, name in _iter_defined_names(ctx):
        if name in blacklist:
            ctx.report(node, f"Blacklisted variable name: {name}")


def _check_wps111(ctx: RuleContext) -> None:
    min_len = H.cfg_int(ctx, "min_name_length", 2)
    allowed = set(H.cfg_list(ctx, "allowed_domain_names"))
    stem = H.module_stem(ctx.path)
    if H.effective_name_length(stem) < min_len and stem not in allowed:
        roots = ctx.document.select(("module",))
        if roots:
            ctx.report(roots[0], f"Module name is too short: {stem}")
    for node, name in _iter_defined_names(ctx):
        if name in allowed or name in ("_", "self", "cls", "mcs"):
            continue
        if H.effective_name_length(name) < min_len:
            ctx.report(node, f"Name is too short: {name}")


def _check_wps112(ctx: RuleContext) -> None:
    for node, name in _iter_defined_names(ctx):
        if name.startswith("__") and name.endswith("__"):
            continue  # dunder ok
        if H.PRIVATE_NAME_PATTERN.match(name):
            ctx.report(node, f"Private name pattern is forbidden: {name}")


def _check_wps113(ctx: RuleContext) -> None:
    for node in ctx.document.select(("aliased_import",)):
        idents = [c for c in H.walk_subtree(ctx, node) if c.kind == "identifier"]
        if len(idents) >= 2 and idents[0].text() == idents[-1].text():
            ctx.report(node, "Import alias is the same as the original name")


def _check_wps114(ctx: RuleContext) -> None:
    for node, name in _iter_defined_names(ctx):
        if H.UNDERSCORED_NUMBER.search(name):
            ctx.report(node, f"Underscored number in name: {name}")


def _check_wps115(ctx: RuleContext) -> None:
    enum_bases = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"} | set(
        H.cfg_list(ctx, "known_enum_bases")
    )
    for cls in ctx.document.select(("class_definition",)):
        # skip enum-like
        bases_text = cls.text().split(":", 1)[0]
        if any(b in bases_text for b in enum_bases):
            continue
        block = H.first_child_kind(ctx, cls, "block")
        if block is None:
            continue
        for child in ctx.children(block):
            if child.kind != "expression_statement" and child.kind != "assignment":
                # class body assignment
                pass
            if child.kind == "assignment" or (
                child.kind == "expression_statement"
                and any(c.kind == "assignment" for c in ctx.children(child))
            ):
                assign = child if child.kind == "assignment" else H.first_child_kind(ctx, child, "assignment")
                if assign is None:
                    continue
                for c in ctx.children(assign):
                    if c.kind == "identifier":
                        name = c.text()
                        if name.isupper() and "_" in name or (name.isupper() and len(name) > 1):
                            if name == name.upper() and any(ch.isalpha() for ch in name):
                                ctx.report(c, f"Class attribute should be snake_case: {name}")
                        break


def _check_wps116(ctx: RuleContext) -> None:
    for node, name in _iter_defined_names(ctx):
        if name.startswith("__") and name.endswith("__"):
            continue
        core = name.strip("_")
        if "__" in core:
            ctx.report(node, f"Consecutive underscores in name: {name}")


def _check_wps117(ctx: RuleContext) -> None:
    reserved = {"self", "cls", "mcs"}
    for node in ctx.document.select(("function_definition", "lambda")):
        names = H.param_names(ctx, node) if node.kind != "lambda" else []
        if node.kind == "lambda":
            params = H.first_child_kind(ctx, node, "lambda_parameters") or H.first_child_kind(
                ctx, node, "parameters"
            )
            if params:
                for c in H.walk_subtree(ctx, params):
                    if c.kind == "identifier" and c.text() in reserved:
                        ctx.report(c, f"Reserved argument name: {c.text()}")
            continue
        # only flag if used outside first method arg
        for i, name in enumerate(names):
            if name in reserved and not (
                i == 0 and H.enclosing_class(ctx, node) is not None
            ):
                # first arg of method is ok
                if i == 0 and H.enclosing_class(ctx, node) is not None:
                    continue
                # find param node
                for p in ctx.document.select(("identifier",)):
                    if p.text() == name and any(a.id == node.id for a in ctx.ancestors(p)):
                        ctx.report(p, f"Reserved argument name: {name}")
                        break


def _check_wps118(ctx: RuleContext) -> None:
    max_len = H.cfg_int(ctx, "max_name_length", 45)
    stem = H.module_stem(ctx.path)
    if len(stem) > max_len:
        roots = ctx.document.select(("module",))
        if roots:
            ctx.report(roots[0], f"Module name is too long: {stem}")
    for node, name in _iter_defined_names(ctx):
        if len(name) > max_len:
            ctx.report(node, f"Name is too long: {name}")


def _check_wps119(ctx: RuleContext) -> None:
    stem = H.module_stem(ctx.path)
    if not H.is_ascii_name(stem):
        roots = ctx.document.select(("module",))
        if roots:
            ctx.report(roots[0], f"Unicode module name: {stem}")
    for node, name in _iter_defined_names(ctx):
        if not H.is_ascii_name(name):
            ctx.report(node, f"Unicode name: {name}")


def _check_wps120(ctx: RuleContext) -> None:
    for node, name in _iter_defined_names(ctx):
        if not name.endswith("_") or name.endswith("__"):
            continue
        base = name[:-1]
        if base not in H.BUILTIN_NAMES and not keyword.iskeyword(base):
            ctx.report(node, f"Unnecessary trailing underscore: {name}")


def _check_wps121(ctx: RuleContext) -> None:
    for func in ctx.document.select(("function_definition",)):
        # find assignments to _name then uses
        unused_defs: dict[str, object] = {}
        for node in H.walk_subtree(ctx, func):
            if node.kind == "assignment":
                for child in ctx.children(node):
                    if child.kind == "identifier" and child.text().startswith("_") and child.text() != "_":
                        unused_defs[child.text()] = child
                        break
        for node in H.walk_subtree(ctx, func):
            if node.kind == "identifier" and node.text() in unused_defs:
                parent = ctx.parent(node)
                if parent is not None and parent.kind == "assignment":
                    # left-hand def
                    kids = ctx.children(parent)
                    if kids and kids[0].id == node.id:
                        continue
                ctx.report(node, f"Unused variable is used: {node.text()}")


def _check_wps122(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("=",)]
        if not kids:
            continue
        left = kids[0]
        if left.kind == "identifier" and left.text().startswith("_"):
            ctx.report(left, "Explicit unused variable in assignment")


def _check_wps123(ctx: RuleContext) -> None:
    for node, name in _iter_defined_names(ctx):
        if re.fullmatch(r"_{2,}", name):
            ctx.report(node, f"Wrong unused variable name: {name}")


def _check_wps124(ctx: RuleContext) -> None:
    stem = H.module_stem(ctx.path)
    if H.has_unreadable_combo(stem):
        roots = ctx.document.select(("module",))
        if roots:
            ctx.report(roots[0], f"Unreadable module name: {stem}")
    for node, name in _iter_defined_names(ctx):
        if H.has_unreadable_combo(name):
            ctx.report(node, f"Unreadable name: {name}")


def _check_wps125(ctx: RuleContext) -> None:
    for node, name in _iter_defined_names(ctx):
        if name in H.BUILTIN_NAMES:
            ctx.report(node, f"Name shadows builtin: {name}")


_CHECKS: dict[str, tuple] = {
    'WPS100': (_check_wps100, ()),
    'WPS101': (_check_wps101, ()),
    'WPS102': (_check_wps102, ()),
    'WPS110': (_check_wps110, ()),
    'WPS111': (_check_wps111, ()),
    'WPS112': (_check_wps112, ()),
    'WPS113': (_check_wps113, ("aliased_import",)),
    'WPS114': (_check_wps114, ()),
    'WPS115': (_check_wps115, ("class_definition",)),
    'WPS116': (_check_wps116, ()),
    'WPS117': (_check_wps117, ()),
    'WPS118': (_check_wps118, ()),
    'WPS119': (_check_wps119, ()),
    'WPS120': (_check_wps120, ()),
    'WPS121': (_check_wps121, ()),
    'WPS122': (_check_wps122, ("assignment",)),
    'WPS123': (_check_wps123, ()),
    'WPS124': (_check_wps124, ()),
    'WPS125': (_check_wps125, ()),
}


def register() -> list[Rule]:
    return [
        make_rule(code, MESSAGES[code], targets, checker)
        for code, (checker, targets) in _CHECKS.items()
    ]
