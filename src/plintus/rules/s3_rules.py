"""S3G001 — no gc / gc.collect in s3/dao paths (s3.mdc)."""

from __future__ import annotations

from plintus.api import Rule, RuleContext, Severity, resolve_call_name
from plintus.rules.cbp_helpers import call_name_matches, imports_module
from plintus.rules.path_utils import path_under


class NoGcInS3(Rule):
    id = "S3G001"
    message = "Do not use gc/gc.collect in S3 DAO paths"
    severity = Severity.ERROR
    targets = ("import_statement", "import_from_statement", "call")

    def check(self, ctx: RuleContext) -> None:
        if not _is_s3_path(ctx.path):
            return
        for node in ctx.nodes:
            if node.kind in ("import_statement", "import_from_statement"):
                if imports_module(node.text(), "gc"):
                    ctx.report(node, "Do not import gc in S3 DAO paths")
                continue
            name = resolve_call_name(ctx.document, node)
            if _is_gc_collect(name):
                ctx.report(node, "Do not call gc.collect in S3 DAO paths")


def _is_gc_collect(name: str | None) -> bool:
    """True for ``gc.collect`` or ``….gc.collect`` (not ``bagcollector.collect``)."""
    if not name or not call_name_matches(name, "collect"):
        return False
    if name == "gc.collect":
        return True
    # Receiver must be exactly ``gc`` or end with ``.gc`` (attribute chain).
    return name.endswith(".gc.collect")


def _is_s3_path(path: str) -> bool:
    if path_under(path, "dao", "s3") or path_under(path, "infra", "s3"):
        return True
    # flat dao/s3.py or infra/s3.py (not any path with an "s3" segment)
    lower = path.replace("\\", "/").lower()
    if lower.endswith("/s3.py") or lower == "s3.py":
        return True
    return False
