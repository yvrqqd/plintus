"""Shared CST helpers for CBP rules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from plintus.api import RuleContext

if TYPE_CHECKING:
    from plintus.document import Node


_LOG_METHODS = frozenset({"info", "warning", "error", "debug", "critical", "exception"})
# Receivers that look like logging loggers (not arbitrary `.info` / `.error` APIs).
_KNOWN_LOGGER_NAMES = frozenset({"logging", "log", "logger", "LOG", "LOGGER"})


def final_segment(name: str | None) -> str | None:
    if not name:
        return None
    return name.rsplit(".", 1)[-1]


def imports_module(text: str, module: str) -> bool:
    """True if ``text`` imports ``module`` or a submodule, not a prefix lookalike.

    Matches ``import module``, ``import module.sub``, ``from module …``,
    and multi-import forms like ``import sys, module``. Does not match
    ``moduleutils`` / ``module_extra`` / ``app.dao_extra``.
    """
    text = text.replace("\n", " ").strip()
    if text.startswith(f"from {module} ") or text.startswith(f"from {module}."):
        return True
    if not text.startswith("import "):
        return False
    for part in text[len("import ") :].split(","):
        name = part.strip().split(None, 1)[0] if part.strip() else ""
        if name == module or name.startswith(f"{module}."):
            return True
    return False


def call_argument_list(ctx: RuleContext, call_node: "Node") -> "Node | None":
    for child in ctx.children(call_node):
        if child.kind == "argument_list":
            return child
    return None


def positional_args(ctx: RuleContext, call_node: "Node") -> list["Node"]:
    args = call_argument_list(ctx, call_node)
    if args is None:
        return []
    out: list[Node] = []
    for child in ctx.children(args):
        if child.kind in ("(", ")", ","):
            continue
        if child.kind == "keyword_argument":
            continue
        out.append(child)
    return out


def keyword_args(ctx: RuleContext, call_node: "Node") -> dict[str, "Node"]:
    args = call_argument_list(ctx, call_node)
    if args is None:
        return {}
    out: dict[str, Node] = {}
    for child in ctx.children(args):
        if child.kind != "keyword_argument":
            continue
        kids = [c for c in ctx.children(child) if c.kind not in ("=",)]
        if len(kids) >= 2 and kids[0].kind == "identifier":
            out[kids[0].text()] = kids[1]
    return out


def keyword_arg_names(ctx: RuleContext, call_node) -> set[str]:
    return set(keyword_args(ctx, call_node))


def is_stringish(node) -> bool:
    return node.kind in ("string", "concatenated_string")


def is_fstring_node(node) -> bool:
    text = node.text()
    i = 0
    while i < len(text) and text[i].lower() in "rufb":
        if text[i].lower() == "f":
            return True
        i += 1
    return False


def class_name(ctx: RuleContext, class_node) -> str | None:
    for child in ctx.children(class_node):
        if child.kind == "identifier":
            return child.text()
    return None


def class_base_names(ctx: RuleContext, class_node) -> list[str]:
    """Dotted base names from a class argument_list (skip keyword args)."""
    names: list[str] = []
    for child in ctx.children(class_node):
        if child.kind != "argument_list":
            continue
        for arg in ctx.children(child):
            if arg.kind in ("(", ")", ","):
                continue
            if arg.kind == "keyword_argument":
                continue
            name = _expr_dotted(ctx, arg)
            if name:
                names.append(name)
    return names


def _expr_dotted(ctx: RuleContext, node) -> str | None:
    if node.kind == "identifier":
        return node.text()
    if node.kind == "attribute":
        parts: list[str] = []
        cur = node
        while cur is not None:
            if cur.kind == "identifier":
                parts.append(cur.text())
                break
            if cur.kind == "attribute":
                children = ctx.children(cur)
                idents = [c for c in children if c.kind == "identifier"]
                objs = [c for c in children if c.kind in ("identifier", "attribute")]
                if idents:
                    parts.append(idents[-1].text())
                cur = objs[0] if objs and objs[0].id != idents[-1].id else None
                continue
            break
        parts.reverse()
        return ".".join(parts) if parts else None
    return None


def class_has_slots(ctx: RuleContext, class_node) -> bool:
    return class_slots_names(ctx, class_node) is not None


def class_slots_names(ctx: RuleContext, class_node) -> list[str] | None:
    """Return ``__slots__`` entry names, or ``None`` if the class has no ``__slots__``."""
    assign = _find_slots_assignment(ctx, class_node)
    if assign is None:
        return None
    right = _assignment_rhs(ctx, assign)
    if right is None:
        return []
    return _slots_entries_from_rhs(ctx, right)


def _find_slots_assignment(ctx: RuleContext, class_node):
    for child in ctx.children(class_node):
        if child.kind == "block":
            for stmt in ctx.children(child):
                assign = _slots_assign_from_stmt(ctx, stmt)
                if assign is not None:
                    return assign
        assign = _slots_assign_from_stmt(ctx, child)
        if assign is not None:
            return assign
    for assign in ctx.document.select(["assignment"]):
        if not _assignment_is_slots(ctx, assign):
            continue
        if not any(a.id == class_node.id for a in ctx.ancestors(assign)):
            continue
        nested_fn = False
        under_class = False
        for anc in ctx.ancestors(assign):
            if anc.kind == "function_definition":
                nested_fn = True
                break
            if anc.id == class_node.id:
                under_class = True
                break
        if under_class and not nested_fn:
            return assign
    return None


def _slots_assign_from_stmt(ctx: RuleContext, node):
    if node.kind == "assignment" and _assignment_is_slots(ctx, node):
        return node
    if node.kind == "expression_statement":
        for child in ctx.children(node):
            if child.kind == "assignment" and _assignment_is_slots(ctx, child):
                return child
    return None


def _assignment_rhs(ctx: RuleContext, assign):
    kids = [c for c in ctx.children(assign) if c.kind not in ("=", ":")]
    if len(kids) < 2:
        return None
    # skip type annotation node if present: __slots__: tuple[str, ...] = (...)
    if kids[1].kind == "type" and len(kids) >= 3:
        return kids[2]
    return kids[-1]


def _slots_entries_from_rhs(ctx: RuleContext, rhs) -> list[str]:
    if rhs.kind == "string":
        return [_string_literal_content(rhs)]
    if rhs.kind in ("tuple", "list"):
        out: list[str] = []
        for child in ctx.children(rhs):
            if child.kind == "string":
                out.append(_string_literal_content(child))
        return out
    return []


def _string_literal_content(node) -> str:
    text = node.text()
    i = 0
    while i < len(text) and text[i].lower() in "frub":
        i += 1
    body = text[i:]
    if body.startswith('"""') or body.startswith("'''"):
        return body[3:-3] if len(body) >= 6 else body
    if body[:1] in "'\"":
        return body[1:-1] if len(body) >= 2 else body
    return body


def class_has_self_assignments(ctx: RuleContext, class_node) -> bool:
    """True if the class body assigns to ``self.*`` (including in methods)."""
    for assign in ctx.document.select(["assignment"]):
        if not any(a.id == class_node.id for a in ctx.ancestors(assign)):
            continue
        if _assignment_is_slots(ctx, assign):
            continue
        kids = [c for c in ctx.children(assign) if c.kind not in ("=", ":")]
        if not kids:
            continue
        left = kids[0]
        if left.kind == "type":
            continue
        if _is_self_target(ctx, left):
            return True
    return False


def _is_self_target(ctx: RuleContext, node) -> bool:
    if node.kind == "attribute":
        idents = [c for c in ctx.children(node) if c.kind == "identifier"]
        return bool(idents) and idents[0].text() == "self"
    if node.kind == "subscript":
        kids = [c for c in ctx.children(node) if c.kind not in ("[", "]", ",")]
        return bool(kids) and _is_self_target(ctx, kids[0])
    return False


def enclosing_class(ctx: RuleContext, node):
    for anc in ctx.ancestors(node):
        if anc.kind == "class_definition":
            return anc
    return None


def _assignment_is_slots(ctx: RuleContext, assign) -> bool:
    for child in ctx.children(assign):
        if child.kind == "identifier" and child.text() == "__slots__":
            return True
    return False


def function_name(ctx: RuleContext, fn_node) -> str | None:
    for child in ctx.children(fn_node):
        if child.kind == "identifier":
            return child.text()
    return None


def decorator_names(ctx: RuleContext, fn_node) -> list[str]:
    from plintus.rules.require_decorator import _decorator_names

    return _decorator_names(ctx, fn_node)


def call_name_matches(name: str | None, *candidates: str) -> bool:
    if not name:
        return False
    short = final_segment(name)
    for c in candidates:
        if name == c or short == c or name.endswith("." + c):
            return True
    return False


def function_param_names(ctx: RuleContext, fn_node) -> list[str]:
    """Parameter identifier names for a ``function_definition``."""
    names: list[str] = []
    params = None
    for child in ctx.children(fn_node):
        if child.kind == "parameters":
            params = child
            break
    if params is None:
        return names
    for param in ctx.children(params):
        if param.kind in ("(", ")", ",", "/", "*"):
            continue
        if param.kind == "identifier":
            names.append(param.text())
            continue
        if param.kind in (
            "default_parameter",
            "typed_parameter",
            "typed_default_parameter",
            "list_splat_pattern",
            "dictionary_splat_pattern",
        ):
            for child in ctx.children(param):
                if child.kind == "identifier":
                    names.append(child.text())
                    break
    return names


# SQL/DAO client method names and likely receivers (shared by G003 / SQL001).
_SQL_DAO_METHODS = frozenset(
    {
        "execute",
        "executemany",
        "fetch",
        "fetchrow",
        "fetchone",
        "fetchall",
        "acquire",
    }
)
_SQL_DAO_RECEIVERS = frozenset(
    {
        "cur",
        "cursor",
        "conn",
        "connection",
        "pool",
        "session",
        "db",
        "engine",
        "executor",
        "client",
        "dao",
        "pg",
        "postgres",
        "asyncpg",
        "aiopg",
        "sa",
        "mysql",
        "sqlite",
    }
)


def looks_like_sql_dao_call(name: str | None) -> bool:
    """Match SQL/DAO client methods, not arbitrary ``.execute`` / ``.fetch`` APIs."""
    if not name or "." not in name:
        return False
    short = name.rsplit(".", 1)[-1]
    if short not in _SQL_DAO_METHODS:
        return False
    receiver = name.rsplit(".", 1)[0]
    parts = [p for p in receiver.replace(".", " ").split() if p]
    lowered = [p.lower() for p in parts]
    if any(p in _SQL_DAO_RECEIVERS for p in lowered):
        return True
    if any("dao" in p for p in lowered):
        return True
    return False


def is_log_method_call(
    name: str | None,
    message_calls: Sequence[str] | None = None,
) -> bool:
    """True for ``logging.*`` / known logger receivers / configured message-calls.

    Avoids treating arbitrary ``response.info(...)``-style APIs as logging.
    """
    if not name:
        return False
    method = final_segment(name)
    if method not in _LOG_METHODS:
        return False
    if name.startswith("logging."):
        return True
    if "." in name:
        receiver = name.rsplit(".", 1)[0]
        recv = receiver.rsplit(".", 1)[-1]
        if recv in _KNOWN_LOGGER_NAMES:
            return True
    if message_calls:
        names = set(message_calls)
        if name in names:
            return True
        # Allow configured short forms that are log methods (rare).
        if name in _LOG_METHODS and name in names:
            return True
    return False
