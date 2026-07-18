"""WPS complexity rules (clean-room port of wemake-python-styleguide codes)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from plintus.api import Rule, RuleContext
from plintus.rules.wps import helpers as H
from plintus.rules.wps._factory import make_rule

if TYPE_CHECKING:
    from plintus.document import Node


def _check_wps200(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_jones_score", 12)
    score = H.jones_score(ctx)
    if score > limit:
        roots = ctx.document.select(("module",))
        node = roots[0] if roots else (ctx.nodes[0] if ctx.nodes else None)
        if node is not None:
            ctx.report(node, f"Jones score is too high: {score} > {limit}")


def _check_wps201(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_imports", 12)
    imports = ctx.document.select(("import_statement", "import_from_statement"))
    if len(imports) > limit:
        ctx.report(imports[0], f"Too many imports: {len(imports)} > {limit}")


def _check_wps202(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_module_members", 7)
    members = ctx.document.select(("function_definition", "class_definition"))
    # only module-level
    top = [m for m in members if not any(a.kind in H.FUNCTION_KINDS | H.CLASS_KINDS for a in ctx.ancestors(m))]
    if len(top) > limit:
        ctx.report(top[0], f"Too many module members: {len(top)} > {limit}")


def _check_wps203(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_imported_names", 50)
    total = 0
    first = None
    for node in ctx.document.select(("import_statement", "import_from_statement")):
        n = H.import_names_count(ctx, node)
        total += n
        if first is None:
            first = node
    if first is not None and total > limit:
        ctx.report(first, f"Too many imported names: {total} > {limit}")


def _check_wps204(ctx: RuleContext) -> None:
    from collections import Counter

    expr_kinds = ("call", "attribute", "binary_operator", "comparison_operator")
    module_limit = H.cfg_int(ctx, "max_module_expressions", 7)
    func_limit = H.cfg_int(ctx, "max_function_expressions", 4)

    module_texts: list[str] = []
    for kind in expr_kinds:
        for node in ctx.document.select((kind,)):
            if H.enclosing_function(ctx, node) is None:
                module_texts.append(node.text())
    for text, count in Counter(module_texts).items():
        if count > module_limit:
            for node in ctx.document.select(expr_kinds):
                if node.text() == text and H.enclosing_function(ctx, node) is None:
                    ctx.report(node, f"Overused expression: used {count} times > {module_limit}")
                    break

    for func in ctx.document.select(("function_definition",)):
        texts: list[str] = []
        for node in H.walk_subtree(ctx, func):
            if node.kind not in expr_kinds:
                continue
            enc = H.enclosing_function(ctx, node)
            if enc is None or enc.id != func.id:
                continue
            texts.append(node.text())
        for text, count in Counter(texts).items():
            if count <= func_limit:
                continue
            for node in H.walk_subtree(ctx, func):
                if node.kind in expr_kinds and node.text() == text:
                    enc = H.enclosing_function(ctx, node)
                    if enc is not None and enc.id == func.id:
                        ctx.report(
                            node,
                            f"Overused expression in function: used {count} times > {func_limit}",
                        )
                        break
            break


def _check_count_in_funcs(ctx: RuleContext, kind: str, key: str, default: int, code_msg: str) -> None:
    limit = H.cfg_int(ctx, key, default)
    for node in ctx.nodes:
        n = H.count_kind_in_subtree(ctx, node, kind)
        if n > limit:
            ctx.report(node, f"{code_msg}: {n} > {limit}")


def _check_wps210(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_local_variables", 5)
    for node in ctx.nodes:
        assigns = H.count_kind_in_subtree(ctx, node, "assignment")
        if assigns > limit:
            ctx.report(node, f"Too many local variables: {assigns} > {limit}")


def _check_wps211(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_arguments", 5)
    for node in ctx.nodes:
        n = H.countable_param_count(ctx, node)
        if n > limit:
            ctx.report(node, f"Too many arguments: {n} > {limit}")


def _check_wps212(ctx: RuleContext) -> None:
    _check_count_in_funcs(ctx, "return_statement", "max_returns", 5, "Too many returns")


def _check_wps213(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_expressions", 9)
    for node in ctx.nodes:
        body = H.function_body(ctx, node)
        if body is None:
            continue
        # count expression statements roughly
        n = H.count_kind_in_subtree(ctx, body, "expression_statement")
        if n > limit:
            ctx.report(node, f"Too many expressions: {n} > {limit}")


def _check_wps214(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_methods", 7)
    for node in ctx.nodes:
        methods = [
            c for c in H.walk_subtree(ctx, node)
            if c.kind in H.FUNCTION_KINDS and H.enclosing_class(ctx, c) is node
        ]
        # only direct methods: function whose enclosing class is this and no nested class between
        methods = []
        for c in H.walk_subtree(ctx, node):
            if c.kind not in H.FUNCTION_KINDS:
                continue
            classes = [a for a in ctx.ancestors(c) if a.kind in H.CLASS_KINDS]
            if classes and classes[0].id == node.id:
                methods.append(c)
        if len(methods) > limit:
            ctx.report(node, f"Too many methods: {len(methods)} > {limit}")


def _check_wps215(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_base_classes", 3)
    for node in ctx.nodes:
        args = H.first_child_kind(ctx, node, "argument_list")
        if args is None:
            continue
        bases = [
            c for c in ctx.children(args)
            if c.kind not in ("(", ")", ",") and c.kind != "keyword_argument"
        ]
        if len(bases) > limit:
            ctx.report(node, f"Too many base classes: {len(bases)} > {limit}")


def _check_wps216(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_decorators", 5)
    for node in ctx.document.select(("decorated_definition",)):
        decs = [c for c in ctx.children(node) if c.kind == "decorator"]
        if len(decs) > limit:
            ctx.report(decs[0], f"Too many decorators: {len(decs)} > {limit}")


def _check_wps217(ctx: RuleContext) -> None:
    _check_count_in_funcs(ctx, "await", "max_awaits", 5, "Too many awaits")


def _check_wps218(ctx: RuleContext) -> None:
    _check_count_in_funcs(ctx, "assert_statement", "max_asserts", 5, "Too many asserts")


def _check_wps219(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_access_level", 4)
    for node in ctx.nodes:
        if node.kind != "attribute":
            continue
        # only outermost attributes
        parent = ctx.parent(node)
        if parent is not None and parent.kind == "attribute":
            continue
        length = H.attribute_chain_length(ctx, node)
        if length > limit:
            ctx.report(node, f"Too deep access: {length} > {limit}")


def _check_wps220(ctx: RuleContext) -> None:
    # wemake default max nesting is typically 5 (not in config list as max-offset); use 5
    limit = 5
    for node in ctx.nodes:
        depth = H.nesting_depth(ctx, node)
        if depth > limit:
            ctx.report(node, f"Too deep nesting: {depth} > {limit}")


def _check_wps221(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_line_complexity", 14)
    counts = H.line_node_counts(ctx)
    for line, count in counts.items():
        if count > limit:
            # find any node on that line
            for node in ctx.document.select_all():
                if node.line == line and len(node.kind) > 1:
                    ctx.report(node, f"Line is too complex: {count} > {limit}")
                    break


def _check_wps222(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_conditions", 4)
    for node in ctx.nodes:
        if node.kind != "boolean_operator":
            continue
        # count 'and'/'or' tokens roughly via text
        text = node.text()
        n = text.count(" and ") + text.count(" or ")
        if n >= limit:
            ctx.report(node, f"Too many conditions: {n + 1} > {limit}")


def _check_wps223(ctx: RuleContext) -> None:
    limit = 3  # wemake default for elifs
    for node in ctx.nodes:
        elifs = H.count_kind_in_subtree(ctx, node, "elif_clause")
        if elifs > limit:
            ctx.report(node, f"Too many elif branches: {elifs} > {limit}")


def _check_wps224(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        fors = H.count_kind_in_subtree(ctx, node, "for_in_clause")
        if fors > 2:
            ctx.report(node, f"Too many for clauses in comprehension: {fors}")


def _check_wps225(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        excepts = H.count_kind_in_subtree(ctx, node, "except_clause")
        if excepts > 3:
            ctx.report(node, f"Too many except cases: {excepts}")


def _check_wps226(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_string_usages", 3)
    from collections import Counter
    strings = [H.string_content(n) for n in ctx.document.select(("string",)) if len(H.string_content(n)) > 0]
    for content, count in Counter(strings).items():
        if count > limit and content not in ("", " ", "\n"):
            for node in ctx.document.select(("string",)):
                if H.string_content(node) == content:
                    ctx.report(node, f"Overused string literal: used {count} times > {limit}")
                    return


def _check_wps227(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        for ret in [n for n in H.walk_subtree(ctx, node) if n.kind == "return_statement"]:
            for child in ctx.children(ret):
                if child.kind == "tuple":
                    elems = [c for c in ctx.children(child) if c.kind not in ("(", ")", ",")]
                    if len(elems) > 5:
                        ctx.report(child, f"Returning tuple is too long: {len(elems)}")


def _check_wps228(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        # comparison with many operators
        ops = node.text().count("==") + node.text().count("!=") + node.text().count("<") + node.text().count(">")
        if ops > 3:
            ctx.report(node, "Compare expression is too long")


def _check_wps229(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_try_body_length", 1)
    for node in ctx.nodes:
        # try body statements
        for child in ctx.children(node):
            if child.kind == "block":
                stmts = [c for c in ctx.children(child) if c.kind not in ("{", "}")]
                # filter real statements
                stmts = [c for c in stmts if len(c.kind) > 1]
                if len(stmts) > limit:
                    ctx.report(node, f"Try body is too long: {len(stmts)} > {limit}")
                break


def _check_wps230(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_attributes", 6)
    for node in ctx.nodes:
        # self.x = ... in __init__
        attrs = set()
        for assign in [n for n in H.walk_subtree(ctx, node) if n.kind == "assignment"]:
            text = assign.text()
            if text.startswith("self."):
                name = text.split("=")[0].strip()
                if name.startswith("self.") and not name.startswith("self._"):
                    attrs.add(name)
        if len(attrs) > limit:
            ctx.report(node, f"Too many public attributes: {len(attrs)} > {limit}")


def _check_wps231(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_cognitive_score", 12)
    for node in ctx.nodes:
        score = H.cognitive_score(ctx, node)
        if score > limit:
            ctx.report(node, f"Cognitive complexity is too high: {score} > {limit}")


def _check_wps232(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_cognitive_average", 8)
    funcs = ctx.document.select(("function_definition",))
    if not funcs:
        return
    scores = [H.cognitive_score(ctx, f) for f in funcs]
    avg = sum(scores) / len(scores)
    if avg > limit:
        ctx.report(funcs[0], f"Average cognitive complexity is too high: {avg:.1f} > {limit}")


def _check_wps233(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_call_level", 3)
    for node in ctx.nodes:
        # a().b().c()
        depth = 0
        cur: Node | None = node
        while cur is not None and cur.kind == "call":
            depth += 1
            kids = ctx.children(cur)
            cur = kids[0] if kids else None
            if cur is not None and cur.kind == "attribute":
                kids = [
                    c for c in ctx.children(cur) if c.kind in ("call", "identifier", "attribute")
                ]
                cur = kids[0] if kids else None
        if depth > limit:
            ctx.report(node, f"Call chain is too long: {depth} > {limit}")


def _check_wps234(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_annotation_complexity", 3)
    for node in ctx.nodes:
        # type annotations with nested subscripts
        for ann in [n for n in H.walk_subtree(ctx, node) if n.kind in ("type", "type_annotation")]:
            depth = H.count_kind_in_subtree(ctx, ann, "subscript")
            if depth > limit:
                ctx.report(ann, f"Annotation is too complex: {depth} > {limit}")


def _check_wps235(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_import_from_members", 8)
    for node in ctx.nodes:
        if node.kind != "import_from_statement":
            continue
        text = node.text()
        if " import " in text:
            rhs = text.split(" import ", 1)[1]
            if rhs.strip() != "*":
                count = rhs.count(",") + 1
                if count > limit:
                    ctx.report(node, f"Too many imported members: {count} > {limit}")


def _check_wps236(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_tuple_unpack_length", 4)
    for node in ctx.nodes:
        if node.kind != "assignment":
            continue
        left = None
        for child in ctx.children(node):
            if child.kind == "pattern_list" or child.kind == "tuple_pattern" or child.kind == "list_pattern":
                left = child
                break
            if child.kind == "expression_list":
                left = child
                break
        if left is None:
            # try first child tuple
            kids = [c for c in ctx.children(node) if c.kind not in ("=",)]
            if kids and kids[0].kind in ("tuple", "list", "pattern_list", "tuple_pattern"):
                left = kids[0]
        if left is not None:
            elems = [c for c in ctx.children(left) if c.kind not in ("(", ")", "[", "]", ",")]
            if len(elems) > limit:
                ctx.report(node, f"Too many unpack targets: {len(elems)} > {limit}")


def _check_wps237(ctx: RuleContext) -> None:
    for node in ctx.nodes:
        if not H.is_fstring(node):
            continue
        # too many interpolations
        if node.text().count("{") > 3:
            ctx.report(node, "F-string is too complex")


def _check_wps238(ctx: RuleContext) -> None:
    _check_count_in_funcs(ctx, "raise_statement", "max_raises", 3, "Too many raises")


def _check_wps239(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_except_exceptions", 3)
    for node in ctx.nodes:
        if node.kind != "except_clause":
            continue
        # except A, B, C or except (A, B, C)
        text = node.text().split(":", 1)[0]
        if text.count(",") + 1 > limit and "(" in text:
            ctx.report(node, f"Too many exceptions in except: > {limit}")


def _check_wps240(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_type_params", 6)
    for node in ctx.nodes:
        for child in ctx.children(node):
            if "type_param" in child.kind:
                count = H.count_kind_in_subtree(ctx, child, "type_parameter") or H.count_kind_in_subtree(
                    ctx, child, "identifier"
                )
                if count > limit:
                    ctx.report(node, f"Too many type params: {count} > {limit}")


def _check_wps241(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_match_subjects", 7)
    for node in ctx.nodes:
        # match subject
        for child in ctx.children(node):
            if child.kind == "tuple":
                elems = [c for c in ctx.children(child) if c.kind not in ("(", ")", ",")]
                if len(elems) > limit:
                    ctx.report(node, f"Too many match subjects: {len(elems)} > {limit}")


def _check_wps242(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_match_cases", 7)
    for node in ctx.nodes:
        cases = H.count_kind_in_subtree(ctx, node, "case_clause")
        if cases > limit:
            ctx.report(node, f"Too many match cases: {cases} > {limit}")


def _check_wps243(ctx: RuleContext) -> None:
    limit = H.cfg_int(ctx, "max_lines_in_finally", 2)
    for node in ctx.nodes:
        if node.kind != "finally_clause":
            continue
        block = H.first_child_kind(ctx, node, "block")
        if block is None:
            continue
        stmts = [c for c in ctx.children(block) if len(c.kind) > 1]
        if len(stmts) > limit:
            ctx.report(node, f"Finally body is too long: {len(stmts)} > {limit}")


_CHECKS = {
    'WPS200': (_check_wps200, ()),
    'WPS201': (_check_wps201, ()),
    'WPS202': (_check_wps202, ()),
    'WPS203': (_check_wps203, ()),
    'WPS204': (_check_wps204, ()),
    'WPS210': (_check_wps210, ("function_definition",)),
    'WPS211': (_check_wps211, ("function_definition",)),
    'WPS212': (_check_wps212, ("function_definition",)),
    'WPS213': (_check_wps213, ("function_definition",)),
    'WPS214': (_check_wps214, ("class_definition",)),
    'WPS215': (_check_wps215, ("class_definition",)),
    'WPS216': (_check_wps216, ()),
    'WPS217': (_check_wps217, ("function_definition",)),
    'WPS218': (_check_wps218, ("function_definition",)),
    'WPS219': (_check_wps219, ("attribute",)),
    'WPS220': (_check_wps220, ("function_definition",)),
    'WPS221': (_check_wps221, ()),
    'WPS222': (_check_wps222, ("boolean_operator",)),
    'WPS223': (_check_wps223, ("if_statement",)),
    'WPS224': (_check_wps224, ("list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression")),
    'WPS225': (_check_wps225, ("try_statement",)),
    'WPS226': (_check_wps226, ()),
    'WPS227': (_check_wps227, ("function_definition",)),
    'WPS228': (_check_wps228, ("comparison_operator",)),
    'WPS229': (_check_wps229, ("try_statement",)),
    'WPS230': (_check_wps230, ("class_definition",)),
    'WPS231': (_check_wps231, ("function_definition",)),
    'WPS232': (_check_wps232, ()),
    'WPS233': (_check_wps233, ("call",)),
    'WPS234': (_check_wps234, ("function_definition", "class_definition")),
    'WPS235': (_check_wps235, ("import_from_statement",)),
    'WPS236': (_check_wps236, ("assignment",)),
    'WPS237': (_check_wps237, ("string",)),
    'WPS238': (_check_wps238, ("function_definition",)),
    'WPS239': (_check_wps239, ("except_clause",)),
    'WPS240': (_check_wps240, ("function_definition", "class_definition")),
    'WPS241': (_check_wps241, ("match_statement",)),
    'WPS242': (_check_wps242, ("match_statement",)),
    'WPS243': (_check_wps243, ("finally_clause",)),
}


def register() -> list[Rule]:
    from plintus.rules.wps.catalog_data import MESSAGES

    out: list[Rule] = []
    for code, (checker, targets) in _CHECKS.items():
        out.append(make_rule(code, MESSAGES[code], targets, checker))
    return out
