"""A001–A004 — asyncio / HTTP conventions from python.mdc."""

from __future__ import annotations

import re

from plintus.api import Fix, Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import (
    call_argument_list,
    imports_module,
    keyword_arg_names,
    keyword_args,
)


def _asyncio_module_aliases(ctx: RuleContext) -> set[str]:
    """Module names bound to asyncio via ``import asyncio [as X]``."""
    aliases: set[str] = set()
    for node in ctx.document.select(["import_statement"]):
        text = node.text().replace("\n", " ")
        if not text.startswith("import "):
            continue
        for part in text[len("import ") :].split(","):
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                src, _, alias = part.partition(" as ")
                src = src.strip()
                if src == "asyncio" or src.startswith("asyncio."):
                    aliases.add(alias.strip())
            else:
                name = part.split()[0] if part.split() else ""
                if name == "asyncio" or name.startswith("asyncio."):
                    aliases.add("asyncio")
    return aliases


def _asyncio_imported_names(ctx: RuleContext, *wanted: str) -> set[str]:
    """Bare / aliased names from ``from asyncio import get_event_loop [as X]``."""
    want = set(wanted)
    found: set[str] = set()
    for node in ctx.document.select(["import_from_statement"]):
        text = node.text().replace("\n", " ")
        if not re.search(r"\bfrom\s+asyncio\s+import\b", text):
            continue
        after = text.split("import", 1)[-1]
        for part in after.split(","):
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                src, _, alias = part.partition(" as ")
                if src.strip() in want:
                    found.add(alias.strip())
            else:
                name = part.split()[0] if part.split() else ""
                if name in want:
                    found.add(name)
    return found


def _is_asyncio_attr_call(
    name: str | None,
    attr: str,
    module_aliases: set[str],
    bare_names: set[str],
) -> bool:
    """True for ``asyncio.ATTR``, ``alias.ATTR``, or bare name imported from asyncio."""
    if not name:
        return False
    if name in bare_names:
        return True
    # Always accept ``asyncio.ATTR``; also imported module aliases.
    for prefix in module_aliases | {"asyncio"}:
        if name == f"{prefix}.{attr}":
            return True
    return False


class NoGetEventLoop(Rule):
    id = "A001"
    message = "Do not call asyncio.get_event_loop(); use get_running_loop() or Service.run()"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        modules = _asyncio_module_aliases(ctx)
        bare = _asyncio_imported_names(ctx, "get_event_loop")
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if _is_asyncio_attr_call(name, "get_event_loop", modules, bare):
                ctx.report(node)


class NoToThread(Rule):
    id = "A002"
    message = "Do not use asyncio.to_thread; use a dedicated ThreadPoolExecutor via run_in_executor"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        modules = _asyncio_module_aliases(ctx)
        bare = _asyncio_imported_names(ctx, "to_thread")
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if _is_asyncio_attr_call(name, "to_thread", modules, bare):
                ctx.report(node)


class NoRequestsInAsync(Rule):
    """A003: no ``requests`` import in modules that define async functions."""

    id = "A003"
    message = "Do not use requests in async modules; use aiohttp"
    severity = Severity.ERROR
    targets = ("import_statement", "import_from_statement")

    def check(self, ctx: RuleContext) -> None:
        has_async = any(
            n.text().lstrip().startswith("async")
            for n in ctx.document.select(["function_definition"])
        )
        if not has_async:
            return
        for node in ctx.nodes:
            if imports_module(node.text(), "requests"):
                ctx.report(node, "Do not import requests in async modules; use aiohttp")


_FROM_AIOHTTP_WEB = re.compile(r"\bfrom\s+aiohttp\.web\s+import\b")
_APPRUNNER_NAME = re.compile(r"\bAppRunner\b")


def _is_aiohttp_apprunner(name: str | None) -> bool:
    """True for ``web.AppRunner`` / ``aiohttp.web.AppRunner`` (not any AppRunner)."""
    if not name:
        return False
    return name in ("web.AppRunner", "aiohttp.web.AppRunner") or name.endswith(
        ".web.AppRunner"
    )


def _imported_apprunner_aliases(ctx: RuleContext) -> set[str]:
    """Names bound by ``from aiohttp.web import AppRunner [as X]``."""
    aliases: set[str] = set()
    for node in ctx.document.select(["import_from_statement"]):
        text = node.text().replace("\n", " ")
        if not _FROM_AIOHTTP_WEB.search(text):
            continue
        # After ``import``, collect AppRunner / AppRunner as alias
        after = text.split("import", 1)[-1]
        for part in after.split(","):
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                src, _, alias = part.partition(" as ")
                if src.strip() == "AppRunner":
                    aliases.add(alias.strip() or "AppRunner")
            elif _APPRUNNER_NAME.fullmatch(part.split()[0] if part.split() else ""):
                aliases.add("AppRunner")
    return aliases


class AppRunnerHandleSignals(Rule):
    """A004: aiohttp ``web.AppRunner(..., handle_signals=False)``."""

    id = "A004"
    message = "AppRunner must be constructed with handle_signals=False"
    severity = Severity.ERROR
    targets = ("call",)

    def check(self, ctx: RuleContext) -> None:
        imported = _imported_apprunner_aliases(ctx)
        for node in ctx.nodes:
            name = resolve_call_name(ctx.document, node)
            if not (_is_aiohttp_apprunner(name) or (name is not None and name in imported)):
                continue
            kwargs = keyword_arg_names(ctx, node)
            if "handle_signals" not in kwargs:
                args = call_argument_list(ctx, node)
                fix = None
                if args is not None:
                    fix = _insert_handle_signals_false(ctx, args)
                ctx.report(node, "Pass handle_signals=False to AppRunner", fix=fix)
                continue
            val = keyword_args(ctx, node).get("handle_signals")
            if val is not None and val.text() != "False":
                ctx.report(
                    node,
                    "AppRunner handle_signals must be False",
                    fix=Fix.replace(val, "False", safety="safe"),
                )


def _insert_handle_signals_false(ctx: RuleContext, args_node) -> Fix | None:
    """Insert ``handle_signals=False`` before the closing ``)``."""
    kids = list(ctx.children(args_node))
    if not kids or kids[-1].kind != ")":
        return None
    close = kids[-1]
    # Empty call: () → (handle_signals=False)
    non_punct = [c for c in kids if c.kind not in ("(", ")")]
    if not non_punct:
        return Fix.replace(args_node, "(handle_signals=False)", safety="safe")
    return Fix(
        start=close.start,
        end=close.start,
        replacement=", handle_signals=False",
        safety="safe",
    )
