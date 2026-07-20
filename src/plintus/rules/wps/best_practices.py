
"""WPS best-practices rules (WPS4xx)."""

from __future__ import annotations

import re

from plintus.api import Rule, RuleContext, resolve_call_name
from plintus.rules.wps import helpers as H
from plintus.rules.wps._factory import make_rule
from plintus.rules.wps.catalog_data import MESSAGES


def _check_wps400(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comment",)):
        text = node.text()
        if "type:" in text or "noqa" in text or "pragma:" in text:
            # magic comments are restricted when excessive; flag noqa: without codes? skip soft
            if re.search(r"#\s*type:\s*ignore$", text):
                ctx.report(node, "Restricted magic comment")


def _check_wps401(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comment",)):
        if re.match(r"#:\s*$", node.text().strip()) or node.text().strip() == "#:":
            ctx.report(node, "Empty doc comment")


def _check_wps402(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_noqa_comments", 10)
    noqas = [n for n in ctx.document.select(("comment",)) if "noqa" in n.text()]
    if len(noqas) > limit:
        ctx.report(noqas[0], f"Too many noqa comments: {len(noqas)} > {limit}")


def _check_wps403(ctx: RuleContext) -> None:
    pragmas = [n for n in ctx.document.select(("comment",)) if "pragma: no cover" in n.text()]
    if len(pragmas) > 10:
        ctx.report(pragmas[0], "Too many pragma: no cover comments")


def _check_wps404(ctx: RuleContext) -> None:
    for node in ctx.document.select(("default_parameter", "typed_default_parameter")):
        for child in ctx.children(node):
            if child.kind in ("list", "dictionary", "set", "call"):
                ctx.report(node, "Complex default is forbidden")


def _check_wps405(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement",)):
        # for target
        for child in ctx.children(node):
            if child.kind in ("tuple", "list", "pattern_list"):
                # unpacking ok as names; flag if call in target — rare
                if any(c.kind == "call" for c in H.walk_subtree(ctx, child)):
                    ctx.report(child, "Complex loop variable")
                break


def _check_wps406(ctx: RuleContext) -> None:
    for node in ctx.document.select(("with_statement",)):
        if " as " in node.text() and any(c.kind == "tuple" for c in ctx.children(node)):
            # allow simple; flag call in as target
            pass
        for child in H.walk_subtree(ctx, node):
            if child.kind == "as_pattern" or child.kind == "as_pattern_target":
                if any(c.kind == "call" for c in H.walk_subtree(ctx, child)):
                    ctx.report(child, "Complex with target")


def _check_wps407(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        if H.enclosing_function(ctx, node) is not None or H.enclosing_class(ctx, node) is not None:
            continue
        kids = [c for c in ctx.children(node) if c.kind not in ("=",)]
        if len(kids) >= 2 and kids[-1].kind in ("list", "dictionary", "set"):
            ctx.report(node, "Mutable module-level constant")


def _check_wps408(ctx: RuleContext) -> None:
    for node in ctx.document.select(("boolean_operator",)):
        parts = re.split(r"\s+and\s+|\s+or\s+", node.text())
        if len(parts) != len(set(parts)) and len(parts) > 1:
            ctx.report(node, "Duplicate logical conditions")


def _check_wps409(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comparison_operator",)):
        text = node.text()
        ops = []
        for op in ("==", "!=", "<=", ">=", "<", ">", "is not", "is", "not in", "in"):
            if op in text:
                ops.append(op)
        if len(set(ops)) > 1 and any(o in ("==", "!=") for o in ops) and any(o in ("in", "is") for o in ops):
            ctx.report(node, "Heterogeneous comparison operators")


def _check_wps410(ctx: RuleContext) -> None:
    forbidden = H.cfg_list(ctx, "forbidden_module_metadata") or ["copyright", "license"]
    allowed = set(H.cfg_list(ctx, "allowed_module_metadata"))
    forbidden_set = set(forbidden) - allowed
    if not forbidden_set:
        return
    for node in ctx.document.select(("assignment",)):
        if H.in_function(ctx, node) or H.enclosing_class(ctx, node):
            continue
        for child in ctx.children(node):
            if child.kind == "identifier" and child.text() in forbidden_set:
                ctx.report(child, f"Forbidden module-level variable: {child.text()}")


def _check_wps411(ctx: RuleContext) -> None:
    # empty module: only comments/pass
    nodes = [n for n in ctx.document.select_all() if len(n.kind) > 1 and n.kind not in ("module", "comment")]
    if not nodes:
        roots = ctx.document.select(("module",))
        if roots:
            ctx.report(roots[0], "Empty module")


def _check_wps412(ctx: RuleContext) -> None:
    if H.module_stem(ctx.path) != "__init__":
        return
    for kind in ("function_definition", "class_definition", "if_statement", "for_statement"):
        nodes = ctx.document.select((kind,))
        # allow simple assignments/imports
        for node in nodes:
            if kind.startswith("function") or kind.startswith("class") or kind in ("if_statement", "for_statement"):
                ctx.report(node, "Logic inside __init__ module")


def _check_wps413(ctx: RuleContext) -> None:
    for node in ctx.document.select(("function_definition",)):
        if H.enclosing_class(ctx, node) is not None:
            continue
        name = H.def_name(ctx, node)
        if name in ("__getattr__", "__dir__"):
            ctx.report(node, f"Module magic method is forbidden: {name}")


def _check_wps414(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        text = node.text()
        if "=" in text and text.strip().startswith("(") and any(op in text for op in ("+", "-", "call")):
            left = text.split("=", 1)[0]
            if "," in left and "(" in text.split("=", 1)[-1]:
                ctx.report(node, "Tuple unpacking with side-effects")


def _check_wps415(ctx: RuleContext) -> None:
    for try_node in ctx.document.select(("try_statement",)):
        seen = set()
        for exc in [n for n in H.walk_subtree(ctx, try_node) if n.kind == "except_clause"]:
            key = exc.text().split(":", 1)[0]
            if key in seen:
                ctx.report(exc, "Duplicate exception class in except blocks")
            seen.add(key)


def _check_wps416(ctx: RuleContext) -> None:
    for node in ctx.document.select(("list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression")):
        if "yield" in node.text():
            ctx.report(node, "Yield inside comprehension")


def _check_wps417(ctx: RuleContext) -> None:
    for node in ctx.document.select(("dictionary", "set")):
        if node.kind == "dictionary":
            keys = []
            for c in ctx.children(node):
                if c.kind == "pair":
                    kids = [k for k in ctx.children(c) if k.kind not in (":",)]
                    if kids:
                        keys.append(kids[0].text())
            if len(keys) != len(set(keys)):
                ctx.report(node, "Duplicate items in hash")
        else:
            items = [c.text() for c in ctx.children(node) if c.kind not in ("{", "}", ",")]
            if len(items) != len(set(items)):
                ctx.report(node, "Duplicate items in set")


def _check_wps418(ctx: RuleContext) -> None:
    for node in ctx.document.select(("class_definition",)):
        if "BaseException" in node.text().split(":", 1)[0] and "class " in node.text():
            args = H.first_child_kind(ctx, node, "argument_list")
            if args and "BaseException" in args.text():
                ctx.report(node, "Exception inherited from BaseException")


def _check_wps419(ctx: RuleContext) -> None:
    for node in ctx.document.select(("try_statement",)):
        returns = H.count_kind_in_subtree(ctx, node, "return_statement")
        if returns > 1:
            ctx.report(node, "Multiple returning paths in try/except")


def _check_wps420(ctx: RuleContext) -> None:
    # forbid del, global, nonlocal somewhat — check statements
    for kind, label in (("delete_statement", "del"), ("global_statement", "global"), ("nonlocal_statement", "nonlocal")):
        for node in ctx.document.select((kind,)):
            ctx.report(node, f"Forbidden keyword: {label}")


def _check_wps421(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        name = resolve_call_name(ctx.document, node)
        if not name:
            continue
        # Bare name or builtins.* only — not obj.print() / foo.eval().
        if name in H.BANNED_BUILTIN_CALLS or (
            name.startswith("builtins.") and name[9:] in H.BANNED_BUILTIN_CALLS
        ):
            ctx.report(node, f"Forbidden builtin call: {name}")


def _check_wps422(ctx: RuleContext) -> None:
    for node in ctx.document.select(("future_import_statement", "import_from_statement")):
        if "__future__" in node.text():
            # wemake forbids some; flag all future imports as restricted style
            if "annotations" not in node.text():
                ctx.report(node, "Forbidden __future__ import")


def _check_wps423(ctx: RuleContext) -> None:
    for node in ctx.document.select(("raise_statement",)):
        for child in ctx.children(node):
            if child.kind == "identifier" and child.text() == "NotImplemented":
                ctx.report(node, "Raise NotImplemented is forbidden")
                break
            if child.kind == "call":
                name = resolve_call_name(ctx.document, child)
                if name == "NotImplemented":
                    ctx.report(node, "Raise NotImplemented is forbidden")
                    break


def _check_wps424(ctx: RuleContext) -> None:
    for node in ctx.document.select(("raise_statement",)):
        if re.search(r"\bBaseException\b", node.text()):
            ctx.report(node, "Raising BaseException is forbidden")


def _check_wps425(ctx: RuleContext) -> None:
    for node in ctx.document.select(("call",)):
        args = H.first_child_kind(ctx, node, "argument_list")
        if args is None:
            continue
        for child in ctx.children(args):
            if child.kind in ("true", "false", "True", "False") or child.text() in ("True", "False"):
                ctx.report(child, "Boolean passed as positional argument")
                break
            if child.kind == "keyword_argument":
                continue
            if child.kind not in ("(", ")", ","):
                # only flag literal bools
                if child.text() in ("True", "False"):
                    ctx.report(child, "Boolean passed as positional argument")


def _check_wps426(ctx: RuleContext) -> None:
    for node in ctx.document.select(("lambda",)):
        if any(a.kind in ("for_statement", "while_statement") for a in ctx.ancestors(node)):
            ctx.report(node, "Lambda inside loop")


def _check_wps427(ctx: RuleContext) -> None:
    for node in ctx.document.select(("function_definition",)):
        body = H.function_body(ctx, node)
        if body is None:
            continue
        seen_return = False
        for child in ctx.children(body):
            if seen_return and len(child.kind) > 1 and child.kind != "comment":
                ctx.report(child, "Unreachable code")
                break
            if child.kind == "return_statement" or child.kind == "raise_statement":
                seen_return = True


def _is_string_expr_stmt(ctx: RuleContext, node) -> bool:
    for child in ctx.children(node):
        if child.kind == "string":
            return True
        if len(child.kind) > 1:
            return False
    return False


def _is_docstring_stmt(ctx: RuleContext, node) -> bool:
    """First string expression_statement in a module / class / function body."""
    if not _is_string_expr_stmt(ctx, node):
        return False
    parent = ctx.parent(node)
    if parent is None or parent.kind not in ("module", "block"):
        return False
    if parent.kind == "block":
        owner = ctx.parent(parent)
        if owner is None or owner.kind not in (H.FUNCTION_KINDS | H.CLASS_KINDS):
            return False
    for child in ctx.children(parent):
        if child.kind == "comment" or len(child.kind) <= 1:
            continue
        return child.id == node.id
    return False


def _is_stub_ellipsis(ctx: RuleContext, node) -> bool:
    """``...`` as the sole body (ignoring docstring) of a function/class stub."""
    if node.text().strip() != "...":
        return False
    parent = ctx.parent(node)
    if parent is None or parent.kind != "block":
        return False
    owner = ctx.parent(parent)
    if owner is None or owner.kind not in (H.FUNCTION_KINDS | H.CLASS_KINDS):
        return False
    stmts = [c for c in ctx.children(parent) if len(c.kind) > 1 and c.kind != "comment"]
    non_doc = [s for i, s in enumerate(stmts) if not (i == 0 and _is_string_expr_stmt(ctx, s))]
    return len(non_doc) == 1 and non_doc[0].id == node.id


def _check_wps428(ctx: RuleContext) -> None:
    for node in ctx.document.select(("expression_statement",)):
        if _is_docstring_stmt(ctx, node) or _is_stub_ellipsis(ctx, node):
            continue
        text = node.text().strip()
        if text in ("...", "None", "True", "False") or re.fullmatch(r"[\"'].*[\"']", text):
            # statement that does nothing — literal alone
            if not text.startswith("assert") and "(" not in text:
                ctx.report(node, "Statement does nothing")


def _check_wps429(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        # a = b = c
        if node.text().count("=") > 1 and "==" not in node.text():
            ctx.report(node, "Multiple assignments on the same line")


def _check_wps430(ctx: RuleContext) -> None:
    for node in ctx.document.select(("function_definition",)):
        if H.enclosing_function(ctx, node) is not None:
            ctx.report(node, "Nested function is forbidden")


def _check_wps431(ctx: RuleContext) -> None:
    whitelist = set(H.cfg_list(ctx, "nested_classes_whitelist")) or {"Meta", "Params", "Config"}
    for node in ctx.document.select(("class_definition",)):
        outer = H.enclosing_class(ctx, node)
        if outer is not None:
            name = H.def_name(ctx, node)
            if name not in whitelist:
                ctx.report(node, f"Nested class is forbidden: {name}")


def _check_wps432(ctx: RuleContext) -> None:
    allowed = {0, 1, -1, 2, 10, 100}  # pragmatic allowlist of common numbers
    for node in ctx.document.select(("integer", "float")):
        try:
            val = node.text().replace("_", "")
            num = float(val) if "." in val or "e" in val.lower() else int(val, 0)
        except ValueError:
            continue
        if num in allowed:
            continue
        # ignore in enum/assignment to ALL_CAPS and doc contexts
        parent = ctx.parent(node)
        if parent is not None and parent.kind in ("unary_operator",):
            continue
        ctx.report(node, f"Magic number: {node.text()}")


def _check_wps433(ctx: RuleContext) -> None:
    for node in ctx.document.select(("import_statement", "import_from_statement")):
        if H.in_function(ctx, node):
            ctx.report(node, "Nested import is forbidden")


def _check_wps434(ctx: RuleContext) -> None:
    for node in ctx.document.select(("assignment",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("=",)]
        if len(kids) >= 2 and kids[0].text() == kids[-1].text() and kids[0].kind == "identifier":
            ctx.report(node, "Assigning a variable to itself")


def _check_wps435(ctx: RuleContext) -> None:
    for node in ctx.document.select(("binary_operator",)):
        text = node.text()
        if "*" in text and ("[" in text or "list(" in text):
            ctx.report(node, "Multiplying lists is forbidden")


def _check_wps436(ctx: RuleContext) -> None:
    for node in ctx.document.select(("import_statement", "import_from_statement")):
        # from ._x import / import _protected
        text = node.text()
        if re.search(r"import\s+_\w+", text) or re.search(r"from\s+\.*_\w+", text):
            ctx.report(node, "Importing protected module")


def _check_wps437(ctx: RuleContext) -> None:
    for node in ctx.document.select(("attribute",)):
        idents = [c for c in ctx.children(node) if c.kind == "identifier"]
        if len(idents) >= 2:
            base, attr = idents[0].text(), idents[-1].text()
            if attr.startswith("_") and not attr.startswith("__") and base not in ("self", "cls", "mcs"):
                ctx.report(node, f"Protected attribute access: {attr}")


def _check_wps438(ctx: RuleContext) -> None:
    for node in ctx.document.select(("raise_statement",)):
        if "StopIteration" in node.text():
            if any(a.kind in H.FUNCTION_KINDS for a in ctx.ancestors(node)):
                func = H.enclosing_function(ctx, node)
                if func and (H.count_kind_in_subtree(ctx, func, "yield") or "yield" in func.text()):
                    ctx.report(node, "Raising StopIteration inside generator")


def _check_wps439(ctx: RuleContext) -> None:
    for node in ctx.document.select(("string",)):
        text = node.text()
        if text.startswith("b") and "\\u" in text:
            ctx.report(node, "Unicode escape in binary string")


def _check_wps454(ctx: RuleContext) -> None:
    for node in ctx.document.select(("raise_statement",)):
        if re.search(r"\braise\s+Exception\b", node.text()) or re.search(r"\braise\s+BaseException\b", node.text()):
            ctx.report(node, "Raising Exception/BaseException is forbidden")


def _check_wps457(ctx: RuleContext) -> None:
    for node in ctx.document.select(("while_statement",)):
        # while True
        if re.match(r"while\s+True\s*:", node.text()):
            ctx.report(node, "Infinite while True loop is forbidden")


def _check_wps461(ctx: RuleContext) -> None:
    """Forbid configured inline ``# noqa`` / ``# noqa: CODE`` ignores."""
    forbidden = {str(c).upper() for c in H.cfg_list(ctx, "forbidden_inline_ignore")}
    if not forbidden:
        return
    for node in ctx.document.select(("comment",)):
        text = node.text()
        lower = text.lower()
        if "noqa" not in lower:
            continue
        if re.search(r"noqa\s*$", lower) or re.search(r"noqa\s*:\s*$", lower):
            if "*" in forbidden:
                ctx.report(node, "Forbidden bare inline noqa")
            continue
        m = re.search(r"noqa\s*:\s*(.+)$", text, re.IGNORECASE)
        if not m:
            continue
        codes = {c.strip().upper() for c in re.split(r"[\s,]+", m.group(1)) if c.strip()}
        hit = codes & forbidden
        if hit:
            ctx.report(node, f"Forbidden inline ignore: {', '.join(sorted(hit))}")


def _check_wps451(ctx: RuleContext) -> None:
    for node in ctx.document.select(("parameters",)):
        if "/" in node.text():
            ctx.report(node, MESSAGES['WPS451'])


def _check_wps452(ctx: RuleContext) -> None:
    for node in ctx.document.select(("finally_clause",)):
        if any(c.kind in ("break_statement", "continue_statement") for c in H.walk_subtree(ctx, node)):
            ctx.report(node, MESSAGES['WPS452'])


def _check_wps453(ctx: RuleContext) -> None:
    src = ctx.source
    if src.startswith("#!") and "python" not in src.split("\n", 1)[0]:
        roots = ctx.document.select(("module",))
        if roots:
            ctx.report(roots[0], MESSAGES['WPS453'])


def _check_wps456(ctx: RuleContext) -> None:
    for node in ctx.document.select(("call",)):
        lower = node.text().lower()
        if 'float("nan")' in lower or "float('nan')" in lower:
            ctx.report(node, MESSAGES['WPS456'])


def _check_wps464(ctx: RuleContext) -> None:
    for node in ctx.document.select(("comment",)):
        if node.text().strip() in ("#", "# "):
            ctx.report(node, MESSAGES['WPS464'])


def _check_wps467(ctx: RuleContext) -> None:
    for node in ctx.document.select(("raise_statement",)):
        if node.text().strip() == "raise" and not any(
            a.kind == "except_clause" for a in ctx.ancestors(node)
        ):
            ctx.report(node, MESSAGES['WPS467'])


def _check_wps476(ctx: RuleContext) -> None:
    for node in ctx.document.select(("for_statement",)):
        if any(c.kind == "await" for c in H.walk_subtree(ctx, node)):
            ctx.report(node, MESSAGES['WPS476'])


# --- WPS443–WPS481 (planned batch) ---

_UNHASHABLE_KINDS = frozenset({"list", "dictionary", "set", "list_comprehension", "dictionary_comprehension", "set_comprehension"})

# math.e / math.pi / math.tau string forms; match prefixes longer than 3 chars (wemake intent).
_MATH_APPROX_STRINGS = (
    "2.718281828459045",
    "3.141592653589793",
    "6.283185307179586",
)

_ALPHABET_STRINGS = frozenset(
    {
        "abcdefghijklmnopqrstuvwxyz",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    }
)


def _pair_key(ctx: RuleContext, pair):
    for child in ctx.children(pair):
        if child.kind not in (":",):
            return child
    return None


def _is_unhashable_expr(node) -> bool:
    return node is not None and node.kind in _UNHASHABLE_KINDS


def _check_wps443(ctx: RuleContext) -> None:
    """Forbid explicit unhashable types as set items / dict keys."""
    for node in ctx.document.select(("set",)):
        for child in ctx.children(node):
            if child.kind in ("{", "}", ","):
                continue
            if _is_unhashable_expr(child):
                ctx.report(child, MESSAGES["WPS443"])
    for node in ctx.document.select(("dictionary",)):
        for child in ctx.children(node):
            if child.kind != "pair":
                continue
            key = _pair_key(ctx, child)
            if _is_unhashable_expr(key):
                ctx.report(key, MESSAGES["WPS443"])


def _is_valid_kwarg_name(name: str) -> bool:
    return bool(name) and name.isidentifier()


def _check_wps445(ctx: RuleContext) -> None:
    """Forbid incorrectly named keywords in starred dicts."""
    for splat in ctx.document.select(("dictionary_splat",)):
        for child in ctx.children(splat):
            if child.kind != "dictionary":
                continue
            for pair in ctx.children(child):
                if pair.kind != "pair":
                    continue
                key = _pair_key(ctx, pair)
                if key is None or key.kind != "string":
                    continue
                content = H.string_content(key)
                if not _is_valid_kwarg_name(content):
                    ctx.report(key, MESSAGES["WPS445"])


def _check_wps446(ctx: RuleContext) -> None:
    """Forbid approximate math constants (use math.pi / math.e / math.tau)."""
    for node in ctx.document.select(("float",)):
        text = node.text().replace("_", "").lower()
        if "e" in text and not text.startswith(("0x",)):
            # scientific notation — skip heuristic prefix match
            continue
        if len(text) <= 3:
            continue
        if any(approx.startswith(text) for approx in _MATH_APPROX_STRINGS):
            ctx.report(node, MESSAGES["WPS446"])


def _check_wps447(ctx: RuleContext) -> None:
    """Forbid using the alphabet as a string (use string.ascii_*)."""
    for node in ctx.document.select(("string",)):
        if H.is_fstring(node):
            continue
        content = H.string_content(node)
        if content in _ALPHABET_STRINGS:
            ctx.report(node, MESSAGES["WPS447"])


def _check_wps449(ctx: RuleContext) -> None:
    """Forbid float keys in dicts (and float subscript indices)."""
    for node in ctx.document.select(("dictionary",)):
        for child in ctx.children(node):
            if child.kind != "pair":
                continue
            key = _pair_key(ctx, child)
            if key is not None and key.kind == "float":
                ctx.report(key, MESSAGES["WPS449"])
    for node in ctx.document.select(("subscript",)):
        for child in ctx.children(node):
            if child.kind == "float":
                ctx.report(child, MESSAGES["WPS449"])


def _except_type_nodes(ctx: RuleContext, except_clause) -> list:
    """Return the exception-type expression node(s) for an except clause."""
    for child in ctx.children(except_clause):
        if child.kind in ("except", "block", ":", "comment"):
            continue
        if child.kind == "as_pattern":
            for sub in ctx.children(child):
                if sub.kind in ("as", "as_pattern_target"):
                    break
                if sub.kind == "tuple":
                    return [c for c in ctx.children(sub) if c.kind not in ("(", ")", ",")]
                return [sub]
        if child.kind == "tuple":
            return [c for c in ctx.children(child) if c.kind not in ("(", ")", ",")]
        return [child]
    return []


def _is_trivial_except_type(node) -> bool:
    return node.kind in ("identifier", "attribute")


def _check_wps455(ctx: RuleContext) -> None:
    """Forbid non-trivial expressions as except parameters (only Name / Attribute)."""
    for node in ctx.document.select(("except_clause",)):
        for typ in _except_type_nodes(ctx, node):
            if not _is_trivial_except_type(typ):
                ctx.report(typ, MESSAGES["WPS455"])


def _pattern_elements(ctx: RuleContext, pattern) -> list:
    return [c for c in ctx.children(pattern) if c.kind not in ("(", ")", ",")]


def _check_wps460(ctx: RuleContext) -> None:
    """Forbid single-element destructuring: ``a, = ...`` / ``(a,) = ...``."""
    for node in ctx.document.select(("assignment", "augmented_assignment")):
        for child in ctx.children(node):
            if child.kind not in ("pattern_list", "tuple_pattern"):
                continue
            elems = _pattern_elements(ctx, child)
            if len(elems) == 1:
                ctx.report(child, MESSAGES["WPS460"])
            break


def _check_wps469(ctx: RuleContext) -> None:
    """Forbid ``raise e from e``."""
    for node in ctx.document.select(("raise_statement",)):
        if " from " not in node.text():
            continue
        kids = [c for c in ctx.children(node) if c.kind not in ("raise", "from")]
        if len(kids) >= 2 and kids[0].text() == kids[1].text() and kids[0].kind == kids[1].kind:
            ctx.report(node, MESSAGES["WPS469"])


def _check_wps470(ctx: RuleContext) -> None:
    """Forbid kwarg unpacking in class definition: ``class A(**kwargs):``."""
    for node in ctx.document.select(("class_definition",)):
        args = H.first_child_kind(ctx, node, "argument_list")
        if args is None:
            continue
        for child in ctx.children(args):
            if child.kind == "dictionary_splat":
                ctx.report(child, MESSAGES["WPS470"])


def _subscript_has_slice(ctx: RuleContext, node) -> bool:
    return any(c.kind == "slice" for c in ctx.children(node))


def _check_wps471(ctx: RuleContext) -> None:
    """Forbid consecutive slices: ``x[1:][:2]``."""
    for node in ctx.document.select(("subscript",)):
        if not _subscript_has_slice(ctx, node):
            continue
        # Outer subscript whose object is itself a sliced subscript.
        for child in ctx.children(node):
            if child.kind == "subscript" and _subscript_has_slice(ctx, child):
                ctx.report(node, MESSAGES["WPS471"])
                break


def _is_starred_rest(ctx: RuleContext, node) -> bool:
    if node.kind != "list_splat_pattern":
        return False
    # *_ or *_name
    return True


def _check_wps472(ctx: RuleContext) -> None:
    """Forbid getting first element via unpacking: ``first, *_ = items``."""
    for node in ctx.document.select(("assignment",)):
        for child in ctx.children(node):
            if child.kind not in ("pattern_list", "tuple_pattern"):
                continue
            elems = _pattern_elements(ctx, child)
            if len(elems) == 2 and elems[0].kind == "identifier" and _is_starred_rest(ctx, elems[1]):
                ctx.report(child, MESSAGES["WPS472"])
            break


def _check_wps481(ctx: RuleContext) -> None:
    """Forbid for-loops directly under module or class body (leaking loop vars)."""
    for node in ctx.document.select(("for_statement",)):
        parent = ctx.parent(node)
        if parent is None:
            continue
        if parent.kind == "module":
            ctx.report(node, MESSAGES["WPS481"])
            continue
        if parent.kind == "block":
            owner = ctx.parent(parent)
            if owner is not None and owner.kind == "class_definition":
                ctx.report(node, MESSAGES["WPS481"])


def _bool_literal_kind(node) -> str | None:
    if node is None:
        return None
    if node.kind in ("true", "True") or node.text() == "True":
        return "True"
    if node.kind in ("false", "False") or node.text() == "False":
        return "False"
    return None


def _check_wps444(ctx: RuleContext) -> None:
    """Forbid ``False and ...`` / ``True or ...`` short-circuit conditions."""
    for node in ctx.document.select(("boolean_operator",)):
        kids = [c for c in ctx.children(node) if c.kind not in ("and", "or")]
        ops = [c for c in ctx.children(node) if c.kind in ("and", "or")]
        if len(kids) < 2 or not ops:
            continue
        left = _bool_literal_kind(kids[0])
        op = ops[0].kind
        if left == "False" and op == "and":
            ctx.report(node, MESSAGES["WPS444"])
        elif left == "True" and op == "or":
            ctx.report(node, MESSAGES["WPS444"])


def _check_wps468(ctx: RuleContext) -> None:
    """Forbid ``for _, item in enumerate(...)``."""
    for node in ctx.document.select(("for_statement",)):
        # iterable must be enumerate(...)
        call = None
        target = None
        seen_in = False
        for child in ctx.children(node):
            if child.kind == "in":
                seen_in = True
                continue
            if not seen_in and child.kind in ("pattern_list", "tuple_pattern", "identifier"):
                target = child
            if seen_in and child.kind == "call":
                call = child
                break
            if seen_in and child.kind not in ("block", ":"):
                # non-call iterable
                break
        if call is None or target is None:
            continue
        name = resolve_call_name(ctx.document, call)
        if name != "enumerate":
            continue
        elems = (
            _pattern_elements(ctx, target)
            if target.kind in ("pattern_list", "tuple_pattern")
            else [target]
        )
        if elems and elems[0].kind == "identifier" and elems[0].text() == "_":
            ctx.report(node, MESSAGES["WPS468"])


def _import_from_module(ctx: RuleContext, node) -> str | None:
    for child in ctx.children(node):
        if child.kind == "dotted_name":
            return child.text()
        if child.kind == "relative_import":
            return child.text()
    return None


def _aliased_import_parts(ctx: RuleContext, node) -> tuple[str | None, str | None]:
    """Return (original_name, alias) for an aliased_import node."""
    original = None
    alias = None
    for child in ctx.children(node):
        if child.kind in ("dotted_name", "identifier"):
            if original is None:
                original = child.text()
            else:
                alias = child.text()
    return original, alias


def _record_import_alias(
    seen: dict[tuple[str, str], dict[str, object]],
    mod: str,
    original: str,
    alias: str,
    node,
    ctx: RuleContext,
) -> None:
    key = (mod, original)
    aliases = seen.setdefault(key, {})
    if aliases and alias not in aliases:
        ctx.report(node, MESSAGES["WPS474"])
    aliases[alias] = node


def _check_wps474(ctx: RuleContext) -> None:
    """Forbid importing the same object under different aliases in one module."""
    seen: dict[tuple[str, str], dict[str, object]] = {}
    for node in ctx.document.select(("import_from_statement",)):
        mod = _import_from_module(ctx, node)
        if mod is None:
            continue
        after_import = False
        for child in ctx.children(node):
            if child.kind == "import":
                after_import = True
                continue
            if not after_import:
                continue
            if child.kind == "dotted_name":
                original = child.text()
                _record_import_alias(seen, mod, original, original, child, ctx)
            elif child.kind == "aliased_import":
                original, alias = _aliased_import_parts(ctx, child)
                if original and alias:
                    _record_import_alias(seen, mod, original, alias, child, ctx)


# Explicit map for codes with dedicated checkers
_EXPLICIT = {
    'WPS400': (_check_wps400, ()),
    'WPS401': (_check_wps401, ()),
    'WPS402': (_check_wps402, ()),
    'WPS403': (_check_wps403, ()),
    'WPS404': (_check_wps404, ()),
    'WPS405': (_check_wps405, ()),
    'WPS406': (_check_wps406, ()),
    'WPS407': (_check_wps407, ()),
    'WPS408': (_check_wps408, ()),
    'WPS409': (_check_wps409, ()),
    'WPS410': (_check_wps410, ()),
    'WPS411': (_check_wps411, ()),
    'WPS412': (_check_wps412, ()),
    'WPS413': (_check_wps413, ()),
    'WPS414': (_check_wps414, ()),
    'WPS415': (_check_wps415, ()),
    'WPS416': (_check_wps416, ()),
    'WPS417': (_check_wps417, ()),
    'WPS418': (_check_wps418, ()),
    'WPS419': (_check_wps419, ()),
    'WPS420': (_check_wps420, ()),
    'WPS421': (_check_wps421, ("call",)),
    'WPS422': (_check_wps422, ()),
    'WPS423': (_check_wps423, ()),
    'WPS424': (_check_wps424, ()),
    'WPS425': (_check_wps425, ()),
    'WPS426': (_check_wps426, ()),
    'WPS427': (_check_wps427, ()),
    'WPS428': (_check_wps428, ()),
    'WPS429': (_check_wps429, ()),
    'WPS430': (_check_wps430, ()),
    'WPS431': (_check_wps431, ()),
    'WPS432': (_check_wps432, ()),
    'WPS433': (_check_wps433, ()),
    'WPS434': (_check_wps434, ()),
    'WPS435': (_check_wps435, ()),
    'WPS436': (_check_wps436, ()),
    'WPS437': (_check_wps437, ()),
    'WPS438': (_check_wps438, ()),
    'WPS439': (_check_wps439, ()),
    'WPS443': (_check_wps443, ()),
    'WPS444': (_check_wps444, ()),
    'WPS445': (_check_wps445, ()),
    'WPS446': (_check_wps446, ()),
    'WPS447': (_check_wps447, ()),
    'WPS449': (_check_wps449, ()),
    'WPS451': (_check_wps451, ()),
    'WPS452': (_check_wps452, ()),
    'WPS453': (_check_wps453, ()),
    'WPS454': (_check_wps454, ()),
    'WPS455': (_check_wps455, ()),
    'WPS456': (_check_wps456, ()),
    'WPS457': (_check_wps457, ()),
    'WPS460': (_check_wps460, ()),
    'WPS461': (_check_wps461, ()),
    'WPS464': (_check_wps464, ()),
    'WPS467': (_check_wps467, ()),
    'WPS468': (_check_wps468, ()),
    'WPS469': (_check_wps469, ()),
    'WPS470': (_check_wps470, ()),
    'WPS471': (_check_wps471, ()),
    'WPS472': (_check_wps472, ()),
    'WPS474': (_check_wps474, ()),
    'WPS476': (_check_wps476, ()),
    'WPS481': (_check_wps481, ()),
}


def register() -> list[Rule]:
    # Only register implemented/partial checkers — planned stubs stay in catalog only.
    return [
        make_rule(code, MESSAGES[code], targets, checker)
        for code, (checker, targets) in _EXPLICIT.items()
    ]
