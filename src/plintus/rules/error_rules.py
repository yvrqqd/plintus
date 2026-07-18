"""E001–E005 — errors, DAO lifecycle, slots, module copyright header."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import (
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
                    if name in ("Exception", "BaseException"):
                        ctx.report(child)
                elif child.kind == "identifier" and child.text() in ("Exception", "BaseException"):
                    ctx.report(child)


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
            ctx.report(node, f"Class '{name}' must define __slots__")


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
