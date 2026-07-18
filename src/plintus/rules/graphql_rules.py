"""G001–G003 — GraphQL conventions from graphql.mdc."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import (
    decorator_names,
    function_name,
    function_param_names,
    imports_module,
    looks_like_sql_dao_call,
)
from plintus.rules.path_utils import is_graphql_resolver_path


_BANNED_IMPORT_ROOTS = frozenset({"graphene", "ariadne", "tartiflette"})
_STRAWBERRY_DECORATOR_SHORTS = frozenset(
    {"field", "mutation", "subscription", "resolver"}
)


def _looks_like_resolver(ctx: RuleContext, node) -> bool:
    """True for GraphQL resolvers (``info`` param and/or strawberry field decorators)."""
    params = function_param_names(ctx, node)
    if "info" in params:
        return True
    present = decorator_names(ctx, node)
    shorts = {n.rsplit(".", 1)[-1] for n in present}
    if shorts & _STRAWBERRY_DECORATOR_SHORTS:
        return True
    if any(n == "strawberry" or n.startswith("strawberry.") for n in present):
        return True
    return False


class BanAlternateGraphql(Rule):
    """G001: ban graphene/ariadne/tartiflette stacks."""

    id = "G001"
    message = "Use strawberry-graphql; graphene/ariadne/tartiflette are forbidden"
    severity = Severity.ERROR
    targets = ("import_statement", "import_from_statement")

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            text = node.text()
            for root in _BANNED_IMPORT_ROOTS:
                if imports_module(text, root):
                    ctx.report(node, f"Do not use {root}; use strawberry-graphql")


class ObserveLatencyOnResolvers(Rule):
    """G002: GraphQL resolvers need @observe_latency."""

    id = "G002"
    message = "GraphQL resolvers must use @observe_latency"
    severity = Severity.ERROR
    targets = ("function_definition",)

    def check(self, ctx: RuleContext) -> None:
        if not is_graphql_resolver_path(ctx.path):
            return
        for node in ctx.nodes:
            ancs = ctx.ancestors(node)
            if any(a.kind == "function_definition" for a in ancs):
                continue  # nested
            fname = function_name(ctx, node)
            if not fname or fname.startswith("_"):
                continue
            if not _looks_like_resolver(ctx, node):
                continue
            present = decorator_names(ctx, node)
            shorts = {n.rsplit(".", 1)[-1] for n in present}
            if "observe_latency" not in shorts:
                ctx.report(node, f"Resolver '{fname}' must be decorated with @observe_latency")


class NoDaoInResolvers(Rule):
    """G003: no DAO/SQL inside resolvers."""

    id = "G003"
    message = "Resolvers must not call DAO/SQL; delegate to managers"
    severity = Severity.ERROR
    targets = ("import_from_statement", "import_statement", "call")

    def check(self, ctx: RuleContext) -> None:
        if not is_graphql_resolver_path(ctx.path):
            return
        for node in ctx.nodes:
            if node.kind in ("import_statement", "import_from_statement"):
                if imports_module(node.text(), "app.dao"):
                    ctx.report(node, "Do not import app.dao in resolvers; use managers")
                continue
            name = resolve_call_name(ctx.document, node)
            if looks_like_sql_dao_call(name):
                ctx.report(node, f"Do not call {name} in resolvers; use managers")
