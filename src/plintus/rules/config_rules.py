"""CFG001–CFG004 — settings / env conventions from project.mdc / python.mdc."""

from __future__ import annotations

import re

from plintus.api import Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import (
    call_name_matches,
    class_base_names,
    class_name,
    keyword_arg_names,
)
from plintus.rules.path_utils import is_test_path, path_under


_SECRET_NAME = re.compile(
    r"(?:^|_)(?:password|pass|secret)$|(?:^|_)api_?key(?:$|_)",
    re.IGNORECASE,
)

# Parents / contexts that bind a name rather than load it.
_ENVIRON_DEF_PARENTS = frozenset(
    {
        "parameters",
        "lambda_parameters",
        "default_parameter",
        "typed_parameter",
        "typed_default_parameter",
        "list_splat_pattern",
        "dictionary_splat_pattern",
        "type",
        "as_pattern_target",
        "function_definition",
        "class_definition",
    }
)


def _environ_is_definition(ctx: RuleContext, node) -> bool:
    """True for params, def/class names, annotations, and assignment/for targets."""
    parent = ctx.parent(node)
    if parent is None:
        return False
    if parent.kind in _ENVIRON_DEF_PARENTS:
        return True
    if parent.kind == "assignment":
        for child in ctx.children(parent):
            if child.kind == "=":
                return node.start < child.start
        return True
    if parent.kind == "for_statement":
        seen_in = False
        for child in ctx.children(parent):
            if child.kind == "in":
                seen_in = True
                continue
            if child.id == node.id:
                return not seen_in
    return False


class NoOsEnviron(Rule):
    """CFG001: no ``os.environ`` / ``from os import environ`` outside tests/."""

    id = "CFG001"
    message = "Do not use os.environ outside tests/; read settings from app.config"
    severity = Severity.ERROR
    targets = ()  # whole-file: attributes, imports, bare environ

    def check(self, ctx: RuleContext) -> None:
        if is_test_path(ctx.path):
            return
        environ_imported = False
        for node in ctx.document.select(["import_from_statement"]):
            text = node.text().replace("\n", " ")
            if re.search(r"\bfrom\s+os\s+import\b", text) and re.search(
                r"\benviron\b", text
            ):
                environ_imported = True
                ctx.report(node, "Do not import environ from os; read settings from app.config")
        for node in ctx.document.select(["attribute"]):
            if node.text() == "os.environ":
                ctx.report(node)
        if not environ_imported:
            return
        for node in ctx.document.select(["identifier"]):
            if node.text() != "environ":
                continue
            if any(a.kind == "import_from_statement" for a in ctx.ancestors(node)):
                continue
            if _environ_is_definition(ctx, node):
                continue
            ctx.report(node, "Do not use environ outside tests/; read settings from app.config")


class SettingsFieldAlias(Rule):
    """CFG002: BaseSettings fields using Field(...) must pass alias=."""

    id = "CFG002"
    message = "Settings Field(...) must include alias='ENV_VAR'"
    severity = Severity.ERROR
    targets = ("class_definition",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            bases = class_base_names(ctx, node)
            if not any(b == "BaseSettings" or b.endswith(".BaseSettings") for b in bases):
                continue
            for call in ctx.document.select(["call"]):
                if not any(a.id == node.id for a in ctx.ancestors(call)):
                    continue
                # Skip nested function bodies
                skip = False
                for a in ctx.ancestors(call):
                    if a.kind == "function_definition":
                        skip = True
                        break
                    if a.id == node.id:
                        break
                if skip:
                    continue
                name = resolve_call_name(ctx.document, call)
                if not call_name_matches(name, "Field"):
                    continue
                if "alias" not in keyword_arg_names(ctx, call):
                    ctx.report(call, "Field(...) must include alias='ENV_VAR'")


class SecretStrForSecrets(Rule):
    """CFG003: password/secret/api_key fields must be annotated SecretStr."""

    id = "CFG003"
    message = "Secret settings fields must use SecretStr"
    severity = Severity.ERROR
    targets = ("class_definition",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            bases = class_base_names(ctx, node)
            if not any(b == "BaseSettings" or b.endswith(".BaseSettings") for b in bases):
                continue
            for assign in ctx.document.select(["assignment"]):
                if not any(a.id == node.id for a in ctx.ancestors(assign)):
                    continue
                skip = False
                for a in ctx.ancestors(assign):
                    if a.kind == "function_definition":
                        skip = True
                        break
                    if a.id == node.id:
                        break
                if skip:
                    continue
                field_name = _annotated_field_name(ctx, assign)
                if field_name is None or not _SECRET_NAME.search(field_name):
                    continue
                type_text = _annotated_type_text(ctx, assign)
                if type_text is None:
                    continue
                if "SecretStr" not in type_text:
                    ctx.report(assign, f"Field '{field_name}' must be annotated SecretStr")


class OneSettingsPerFile(Rule):
    """CFG004: in app/config/, one BaseSettings subclass + one module-level singleton."""

    id = "CFG004"
    message = "app/config/ modules must define exactly one BaseSettings class and one singleton"
    severity = Severity.ERROR
    targets = ()  # whole-file scan

    def check(self, ctx: RuleContext) -> None:
        if not path_under(ctx.path, "app", "config"):
            return
        classes = []
        for node in ctx.document.select(["class_definition"]):
            bases = class_base_names(ctx, node)
            if any(b == "BaseSettings" or b.endswith(".BaseSettings") for b in bases):
                classes.append(node)
        if len(classes) == 0:
            return
        if len(classes) > 1:
            for node in classes[1:]:
                ctx.report(node, "Only one BaseSettings subclass per app/config/ file")
            return
        cls = classes[0]
        cname = class_name(ctx, cls)
        if not cname:
            return
        # Module-level assignment calling ClassName()
        singletons = []
        for assign in ctx.document.select(["assignment"]):
            # must be module-level: ancestors should not include class/function
            ancs = ctx.ancestors(assign)
            if any(a.kind in ("class_definition", "function_definition") for a in ancs):
                continue
            kids = ctx.children(assign)
            # left = identifier, right = call ClassName()
            left = next((c for c in kids if c.kind == "identifier"), None)
            call = next((c for c in kids if c.kind == "call"), None)
            if left is None or call is None:
                continue
            name = resolve_call_name(ctx.document, call)
            if name == cname:
                singletons.append(assign)
        if not singletons:
            ctx.report(cls, f"Missing module-level singleton for {cname} (e.g. {cname.upper()}_SETTINGS = {cname}())")
        elif len(singletons) > 1:
            for s in singletons[1:]:
                ctx.report(s, f"Only one module-level {cname}() singleton per file")


def _annotated_field_name(ctx: RuleContext, assign) -> str | None:
    for child in ctx.children(assign):
        if child.kind == "identifier":
            return child.text()
    return None


def _annotated_type_text(ctx: RuleContext, assign) -> str | None:
    for child in ctx.children(assign):
        if child.kind == "type":
            return child.text()
    return None
