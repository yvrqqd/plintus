"""Shared CST helpers and constants for WPS rules (clean-room)."""

from __future__ import annotations

import builtins
import re
from pathlib import Path
from typing import Iterable

from plintus.api import RuleContext, resolve_call_name

MODULE_NAMES_BLACKLIST = frozenset(
    {
        "utils",
        "utilities",
        "helpers",
        "misc",
        "miscellaneous",
        "core",
        "base",
        "common",
        "shared",
    }
)

VARIABLE_NAMES_BLACKLIST = frozenset(
    {
        "data",
        "result",
        "results",
        "item",
        "items",
        "value",
        "values",
        "val",
        "vals",
        "var",
        "vars",
        "variable",
        "content",
        "contents",
        "info",
        "obj",
        "objects",
        "objs",
        "foo",
        "bar",
        "baz",
        "handle",
        "handler",
        "handlers",
        "param",
        "params",
        "parameters",
        "arg",
        "args",
        "kwarg",
        "kwargs",
        "elem",
        "element",
        "elements",
        "spam",
        "ham",
        "tmp",
        "temp",
        "arr",
    }
)

MAGIC_MODULE_NAMES_WHITELIST = frozenset({"__init__", "__main__"})

UNREADABLE_CHARACTER_COMBINATIONS = frozenset(
    {"0O", "O0", "1l", "l1", "1I", "I1", "0o", "o0"}
)

MAGIC_METHODS_BLACKLIST = frozenset(
    {
        "__del__",
        "__delete__",
        "__delitem__",
        "__delattr__",
    }
)

ASYNC_MAGIC_METHODS_BLACKLIST = frozenset(
    {
        "__init__",
        "__new__",
        "__del__",
        "__iter__",
        "__next__",
        "__enter__",
        "__exit__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
    }
)

YIELD_MAGIC_METHODS_BLACKLIST = frozenset(
    {
        "__init__",
        "__new__",
        "__str__",
        "__repr__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__bool__",
        "__len__",
    }
)

BANNED_BUILTIN_CALLS = frozenset(
    {
        "print",
        "pprint",
        "input",
        "breakpoint",
        "eval",
        "exec",
        "compile",
        "exit",
        "quit",
        "help",
        "dir",
        "vars",
        "locals",
        "globals",
        "copyright",
        "credits",
        "license",
    }
)

BUILTIN_NAMES = frozenset(name for name in dir(builtins) if name[:1] != "_") | frozenset(
    {"True", "False", "None"}
)

ALLOWED_BUILTIN_CLASSES = frozenset(
    {
        "object",
        "type",
        "Exception",
        "BaseException",
        "Warning",
        "UserWarning",
        "DeprecationWarning",
        "PendingDeprecationWarning",
        "SyntaxWarning",
        "RuntimeWarning",
        "FutureWarning",
        "ImportWarning",
        "UnicodeWarning",
        "BytesWarning",
        "ResourceWarning",
    }
)

# tree-sitter-python emits only ``function_definition`` (with an ``async`` child
# for coroutines). There is no ``async_function_definition`` kind.
FUNCTION_KINDS = frozenset({"function_definition"})
CLASS_KINDS = frozenset({"class_definition"})
BLOCK_KINDS = frozenset(
    {
        "if_statement",
        "elif_clause",
        "else_clause",
        "for_statement",
        "while_statement",
        "with_statement",
        "try_statement",
        "except_clause",
        "finally_clause",
        "match_statement",
        "case_clause",
    }
)
COGNITIVE_KINDS = frozenset(
    {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "except_clause",
        "with_statement",
        "boolean_operator",
        "conditional_expression",
        "lambda",
        "list_comprehension",
        "dictionary_comprehension",
        "set_comprehension",
        "generator_expression",
    }
)

MODULE_NAME_PATTERN = re.compile(r"^_?[a-z][_a-z0-9]*$")
PRIVATE_NAME_PATTERN = re.compile(r"^__[^_].*")
UNDERSCORED_NUMBER = re.compile(r"_\d")
CONSECUTIVE_UNDERSCORES = re.compile(r"__")


def module_stem(path: str) -> str:
    return Path(path).stem


def named_children(ctx: RuleContext, node) -> list:
    return [c for c in ctx.children(node) if getattr(c, "kind", None) not in (None,)]


def walk_subtree(ctx: RuleContext, node) -> Iterable:
    stack = [node]
    while stack:
        cur = stack.pop()
        yield cur
        stack.extend(reversed(ctx.children(cur)))


def count_kind_in_subtree(ctx: RuleContext, node, kinds: str | Iterable[str]) -> int:
    wanted = {kinds} if isinstance(kinds, str) else set(kinds)
    return sum(1 for n in walk_subtree(ctx, node) if n.kind in wanted)


def first_child_kind(ctx: RuleContext, node, kind: str):
    for child in ctx.children(node):
        if child.kind == kind:
            return child
    return None


def identifier_text(node) -> str | None:
    if node is None:
        return None
    if node.kind == "identifier":
        return node.text()
    return None


def def_name(ctx: RuleContext, node) -> str | None:
    for child in ctx.children(node):
        if child.kind == "identifier":
            return child.text()
    return None


def is_async_function(ctx: RuleContext, node) -> bool:
    """True if ``node`` is a ``function_definition`` with an ``async`` keyword child."""
    if node.kind != "function_definition":
        return False
    return any(c.kind == "async" for c in ctx.children(node)) or node.text().lstrip().startswith(
        "async"
    )


def function_parameters(ctx: RuleContext, func_node) -> list:
    params = first_child_kind(ctx, func_node, "parameters")
    if params is None:
        return []
    out = []
    for child in ctx.children(params):
        if child.kind in ("(", ")", ",", "/", "*"):
            continue
        out.append(child)
    return out


def param_names(ctx: RuleContext, func_node) -> list[str]:
    names: list[str] = []
    for param in function_parameters(ctx, func_node):
        if param.kind == "identifier":
            names.append(param.text())
        elif param.kind in (
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


def countable_param_count(ctx: RuleContext, func_node) -> int:
    names = param_names(ctx, func_node)
    return sum(1 for n in names if n not in ("self", "cls", "mcs"))


def function_body(ctx: RuleContext, func_node):
    return first_child_kind(ctx, func_node, "block")


def nesting_depth(ctx: RuleContext, node) -> int:
    depth = 0
    best = 0
    for n in walk_subtree(ctx, node):
        if n.kind in BLOCK_KINDS:
            # approximate: count ancestors of same kinds
            d = sum(1 for a in ctx.ancestors(n) if a.kind in BLOCK_KINDS)
            best = max(best, d + 1)
            depth = best
    return depth


def cognitive_score(ctx: RuleContext, func_node) -> int:
    score = 0
    for n in walk_subtree(ctx, func_node):
        if n.kind in COGNITIVE_KINDS:
            nest = sum(1 for a in ctx.ancestors(n) if a.kind in COGNITIVE_KINDS)
            score += 1 + nest
    return score


def effective_name_length(name: str) -> int:
    return len(name.strip("_"))


def is_ascii_name(name: str) -> bool:
    try:
        name.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def has_unreadable_combo(name: str) -> bool:
    for combo in UNREADABLE_CHARACTER_COMBINATIONS:
        if combo in name:
            return True
    return False


def call_name(ctx: RuleContext, call_node) -> str | None:
    return resolve_call_name(ctx.document, call_node)


def attribute_chain_length(ctx: RuleContext, node) -> int:
    length = 0
    cur = node
    while cur is not None and cur.kind == "attribute":
        length += 1
        kids = [c for c in ctx.children(cur) if c.kind in ("identifier", "attribute", "call")]
        cur = kids[0] if kids else None
    return length


def line_node_counts(ctx: RuleContext) -> dict[int, int]:
    counts: dict[int, int] = {}
    for node in ctx.document.select_all():
        if not getattr(node, "kind", None):
            continue
        # count named-ish nodes roughly by excluding punctuation-only
        if len(node.kind) == 1:
            continue
        counts[node.line] = counts.get(node.line, 0) + 1
    return counts


def jones_score(ctx: RuleContext) -> float:
    counts = list(line_node_counts(ctx).values())
    if not counts:
        return 0.0
    counts.sort()
    mid = len(counts) // 2
    if len(counts) % 2:
        return float(counts[mid])
    return (counts[mid - 1] + counts[mid]) / 2.0


def string_content(node) -> str:
    text = node.text()
    # strip prefixes and quotes best-effort
    i = 0
    while i < len(text) and text[i].lower() in "frub":
        i += 1
    body = text[i:]
    if body.startswith('"""') or body.startswith("'''"):
        return body[3:-3] if len(body) >= 6 else body
    if body[:1] in "'\"":
        return body[1:-1] if len(body) >= 2 else body
    return body


def is_fstring(node) -> bool:
    text = node.text()
    i = 0
    while i < len(text) and text[i].lower() in "rub":
        i += 1
    return i < len(text) and text[i].lower() == "f"


def in_function(ctx: RuleContext, node) -> bool:
    return any(a.kind in FUNCTION_KINDS for a in ctx.ancestors(node))


def enclosing_function(ctx: RuleContext, node):
    for a in ctx.ancestors(node):
        if a.kind in FUNCTION_KINDS:
            return a
    return None


def enclosing_class(ctx: RuleContext, node):
    for a in ctx.ancestors(node):
        if a.kind in CLASS_KINDS:
            return a
    return None


def import_names_count(ctx: RuleContext, import_node) -> int:
    return count_kind_in_subtree(ctx, import_node, "dotted_name") + count_kind_in_subtree(
        ctx, import_node, "aliased_import"
    )


def cfg_int(ctx: RuleContext, key: str, default: int) -> int:
    val = ctx.config.get(key, default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def cfg_list(ctx: RuleContext, key: str) -> list:
    val = ctx.config.get(key, [])
    return list(val) if val else []
