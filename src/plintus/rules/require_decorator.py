"""DEC001 — require decorators on matching function definitions (not pydocstyle D)."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, Severity


class RequireDecorator(Rule):
    """Config: require_decorators = { "function_name": ["decorator", ...] }."""

    id = "DEC001"
    message = "Missing required decorator"
    severity = Severity.ERROR
    targets = ("function_definition",)

    def check(self, ctx: RuleContext) -> None:
        required: dict[str, list[str]] = dict(ctx.config.get("require_decorators", {}) or {})
        if not required:
            return
        for node in ctx.nodes:
            fname = _function_name(ctx, node)
            if not fname or fname not in required:
                continue
            present = set(_decorator_names(ctx, node))
            for deco in required[fname]:
                if deco not in present:
                    ctx.report(node, f"Function '{fname}' must be decorated with @{deco}")


def _function_name(ctx: RuleContext, node) -> str | None:
    for child in ctx.children(node):
        if child.kind == "identifier":
            return child.text()
    return None


def _decorator_names(ctx: RuleContext, node) -> list[str]:
    """Collect decorator names.

    tree-sitter-python puts decorators on ``decorated_definition`` as siblings
    of the ``function_definition`` (not as children). So we walk to the parent
    ``decorated_definition`` and collect its ``decorator`` children.

    Each ``decorator`` node has shape ``@<expr>`` where ``<expr>`` is an
    ``identifier`` or ``attribute`` (dotted) optionally followed by a call
    ``(...)``. We resolve the dotted name from the expression sub-nodes rather
    than parsing raw text, so ``@functools.wraps(fn)`` and ``@pkg.login_required``
    work correctly.
    """
    parent = ctx.parent(node)
    if parent is None or parent.kind != "decorated_definition":
        return []
    names: list[str] = []
    for child in ctx.children(parent):
        if child.kind != "decorator":
            continue
        name = _decorator_name(ctx, child)
        if name is not None:
            names.append(name)
    return names


def _decorator_name(ctx: RuleContext, decorator_node) -> str | None:
    """Resolve the dotted name of a ``decorator`` node (without ``@`` and call args)."""
    for child in ctx.children(decorator_node):
        # Skip the leading `@` punctuation; the expression is the first named child.
        if child.kind != "@":
            return _dotted_name(ctx, child)
    return None


def _dotted_name(ctx: RuleContext, expr_node) -> str | None:
    """Resolve ``identifier`` or ``attribute`` (possibly wrapped in a call) to a dotted name."""
    node = expr_node
    # A decorated call: `@deco(...)` — the expression is a `call` whose function is the name.
    if node.kind == "call":
        kids = ctx.children(node)
        if not kids:
            return None
        node = kids[0]
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
