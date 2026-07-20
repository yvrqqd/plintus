"""E001–E006 — errors, DAO lifecycle, slots, module copyright header."""

from __future__ import annotations

from plintus.api import Fix, Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import (
    _assignment_is_slots,
    call_name_matches,
    class_base_names,
    class_has_self_assignments,
    class_has_slots,
    class_name,
    class_slots_names,
    decorator_names,
    enclosing_class,
)
from plintus.rules.path_utils import path_under


_SKIP_BASES = frozenset(
    {
        "Protocol",
        "Enum",
        "IntEnum",
        "StrEnum",
        "TypedDict",
        "Exception",
        "BaseException",
        "ABC",
        "Struct",
        "BaseModel",
        "BaseSettings",
        "NamedTuple",
    }
)

_DATACLASS_DECOS = frozenset({"dataclass", "dataclasses.dataclass"})


_BARE_EXCEPTIONS = frozenset({"Exception", "BaseException"})


class NoBareException(Rule):
    """E001: no raise Exception / raise BaseException."""

    id = "E001"
    message = "Do not raise bare Exception/BaseException; use a typed AppError subclass"
    severity = Severity.ERROR
    targets = ("raise_statement",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            for child in ctx.children(node):
                if child.kind == "call":
                    name = resolve_call_name(ctx.document, child)
                    if name in _BARE_EXCEPTIONS:
                        ctx.report(child)
                elif child.kind == "identifier" and child.text() in _BARE_EXCEPTIONS:
                    ctx.report(child)


class NoCatchBareException(Rule):
    """E006: no ``except Exception`` / ``except BaseException`` (incl. tuples)."""

    id = "E006"
    message = (
        "Do not catch bare Exception/BaseException; "
        "catch specific exception types instead"
    )
    severity = Severity.ERROR
    targets = ("except_clause",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            for ident in _except_type_identifiers(ctx, node):
                if ident.text() in _BARE_EXCEPTIONS:
                    ctx.report(ident)


class DaoNoConnectClose(Rule):
    """E002: DAO under ``app/dao/`` must not call client connect()/close()."""

    id = "E002"
    message = "DAO must not call connect()/close(); connection client owns lifecycle"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        if not path_under(ctx.path, "app", "dao"):
            return
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if call_name_matches(name, "connect", "close"):
                # Avoid false positives on contextlib closing etc. — require attribute call
                if name and "." in name and name.rsplit(".", 1)[-1] in ("connect", "close"):
                    ctx.report(node, f"DAO must not call {name.rsplit('.', 1)[-1]}(); connection client owns lifecycle")


class RequireSlots(Rule):
    """E003: concrete infra/dao classes with ``self.*`` attrs need ``__slots__``."""

    id = "E003"
    message = "Classes in app/infra and app/dao with instance attributes must define __slots__"
    severity = Severity.ERROR
    targets = ("class_definition",)

    def check(self, ctx: RuleContext) -> None:
        if not (
            path_under(ctx.path, "app", "infra") or path_under(ctx.path, "app", "dao")
        ):
            return
        for node in ctx.nodes:
            name = class_name(ctx, node) or "<class>"
            if name.endswith("Mixin"):
                continue
            bases = class_base_names(ctx, node)
            short_bases = {b.rsplit(".", 1)[-1] for b in bases}
            if short_bases & _SKIP_BASES:
                continue
            decos = decorator_names(ctx, node)
            if any(d in _DATACLASS_DECOS or d.rsplit(".", 1)[-1] == "dataclass" for d in decos):
                continue
            if not class_has_self_assignments(ctx, node):
                continue
            if class_has_slots(ctx, node):
                continue
            ctx.report(
                node,
                f"Class '{name}' must define __slots__",
                fix=_slots_fix_for_class(ctx, node),
            )


class CopyrightHeader(Rule):
    """E004: modules must start with a 2–3 line ``#`` copyright, then one blank line."""

    id = "E004"
    message = (
        "Module must start with a 2–3 line # copyright header, "
        "followed by one blank line"
    )
    severity = Severity.ERROR
    targets = ()

    def check(self, ctx: RuleContext) -> None:
        roots = ctx.document.select(("module",))
        if not roots:
            return
        root = roots[0]
        lines = ctx.source.splitlines()
        i = 0
        while i < len(lines) and lines[i].startswith("#"):
            i += 1
        n_comments = i
        if n_comments < 2 or n_comments > 3:
            ctx.report(
                root,
                f"Module must start with a 2–3 line # copyright header "
                f"(found {n_comments})",
            )
            return
        if i >= len(lines) or lines[i] != "":
            ctx.report(root, "Copyright header must be followed by one blank line")
            return
        if i + 1 < len(lines) and lines[i + 1] == "":
            ctx.report(
                root,
                "Copyright header must be followed by exactly one blank line",
            )


class NoSlottedDictAccess(Rule):
    """E005: slotted classes must not use ``self.__dict__`` / ``vars(self)``."""

    id = "E005"
    message = (
        "slotted class must not use self.__dict__ / vars(self); "
        "add attributes to __slots__ instead"
    )
    severity = Severity.ERROR
    targets = ("attribute", "call")

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            cls = enclosing_class(ctx, node)
            if cls is None:
                continue
            slots = class_slots_names(ctx, cls)
            if slots is None or "__dict__" in slots:
                continue
            if node.kind == "attribute" and _is_self_dict_attr(ctx, node):
                ctx.report(node)
            elif node.kind == "call" and _is_vars_self(ctx, node):
                ctx.report(node)


def _except_type_identifiers(ctx: RuleContext, except_clause) -> list:
    """Yield type identifiers from ``except T`` / ``except T as e`` / tuples."""
    out: list = []
    for child in ctx.children(except_clause):
        if child.kind in ("except", ":", "block"):
            continue
        _collect_except_type_idents(ctx, child, out)
    return out


def _collect_except_type_idents(ctx: RuleContext, node, out: list) -> None:
    if node.kind == "identifier":
        out.append(node)
        return
    if node.kind == "as_pattern":
        for child in ctx.children(node):
            if child.kind == "as":
                break
            _collect_except_type_idents(ctx, child, out)
        return
    if node.kind == "tuple":
        for child in ctx.children(node):
            if child.kind in ("(", ")", ","):
                continue
            _collect_except_type_idents(ctx, child, out)
        return
    if node.kind == "attribute":
        idents = [c for c in ctx.children(node) if c.kind == "identifier"]
        if idents:
            out.append(idents[-1])
        return


def _is_self_dict_attr(ctx: RuleContext, node) -> bool:
    idents = [c for c in ctx.children(node) if c.kind == "identifier"]
    return (
        len(idents) >= 2
        and idents[0].text() == "self"
        and idents[-1].text() == "__dict__"
    )


def _is_vars_self(ctx: RuleContext, node) -> bool:
    name = resolve_call_name(ctx.document, node)
    if name != "vars":
        return False
    for child in ctx.children(node):
        if child.kind != "argument_list":
            continue
        args = [c for c in ctx.children(child) if c.kind not in ("(", ")", ",")]
        return len(args) == 1 and args[0].kind == "identifier" and args[0].text() == "self"
    return False


def _slots_fix_for_class(ctx: RuleContext, class_node) -> Fix | None:
    names = _self_slot_names(ctx, class_node)
    if not names:
        return None
    block = None
    for child in ctx.children(class_node):
        if child.kind == "block":
            block = child
            break
    if block is None:
        return None
    body_nodes = list(ctx.children(block))
    if not body_nodes:
        return None
    insert_before = body_nodes[0]
    if _is_docstring_stmt(ctx, insert_before) and len(body_nodes) > 1:
        insert_before = body_nodes[1]
    line_start = ctx.source.rfind("\n", 0, insert_before.start) + 1
    indent = ctx.source[line_start:insert_before.start]
    # Match body indent style (tabs vs spaces) for the nested tuple items.
    unit = "\t" if indent and set(indent) <= {"\t"} else "    "
    slot_indent = indent + unit
    slot_lines = [f"{indent}__slots__ = ("]
    slot_lines.extend(f"{slot_indent}'{name}'," for name in names)
    slot_lines.append(f"{indent})")
    replacement = "\n".join(slot_lines) + "\n\n"
    # Incomplete discovery (setattr / dynamic attrs) can break at runtime.
    return Fix(
        start=line_start,
        end=line_start,
        replacement=replacement,
        safety="unsafe",
    )


def _is_docstring_stmt(ctx: RuleContext, node) -> bool:
    if node.kind != "expression_statement":
        return False
    return any(child.kind == "string" for child in ctx.children(node))


def _self_slot_names(ctx: RuleContext, class_node) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for assign in ctx.document.select(["assignment"]):
        enc = enclosing_class(ctx, assign)
        if enc is None or enc.id != class_node.id:
            continue
        if _assignment_is_slots(ctx, assign):
            continue
        kids = [c for c in ctx.children(assign) if c.kind not in ("=", ":")]
        if not kids:
            continue
        left = kids[0]
        if left.kind != "attribute":
            continue
        idents = [c for c in ctx.children(left) if c.kind == "identifier"]
        if len(idents) < 2 or idents[0].text() != "self":
            continue
        name = idents[-1].text()
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names
