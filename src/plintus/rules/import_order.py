"""I001 — CBP import section order with safe autofix.

Sections (blank line between non-empty groups)::

    stdlib
    third-party
    cbp_*          # top-level name startswith configured prefix
    first-party    # known-first-party or relative imports

``from __future__`` stays in the preamble (with copyright / docstring) and is
not reordered. Mid-block comments between imports are not preserved on ``--fix``.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from plintus.api import Fix, Rule, RuleContext, Severity

if TYPE_CHECKING:
    from plintus.document import Node

_IMPORT_KINDS = frozenset({"import_statement", "import_from_statement"})
_PREAMBLE_KINDS = frozenset(
    {
        "comment",
        "expression_statement",  # module docstring
        "future_import_statement",
    }
)

_SECTION_STDLIB = 0
_SECTION_THIRD = 1
_SECTION_CBP = 2
_SECTION_FIRST = 3

_STDLIB = frozenset(getattr(sys, "stdlib_module_names", ()))


class ImportOrder(Rule):
    """Enforce stdlib → third-party → cbp_* → first-party import sections."""

    id = "I001"
    message = (
        "Imports must be ordered: stdlib, third-party, cbp_*, first-party "
        "(blank line between sections)"
    )
    severity = Severity.WARNING
    targets = ()

    def check(self, ctx: RuleContext) -> None:
        roots = ctx.document.select(("module",))
        if not roots:
            return
        children = ctx.children(roots[0])
        imports = _top_level_import_block(children)
        if len(imports) < 1:
            return

        known_first = list(ctx.config.get("known_first_party", ["app"]))
        cbp_prefix = str(ctx.config.get("cbp_import_prefix", "cbp_"))

        sorted_text = _render_sorted(ctx, imports, known_first, cbp_prefix)
        block_start = imports[0].start
        block_end = imports[-1].end
        replacement = sorted_text
        fix_end = block_end

        # Ensure one blank line after the import block when a non-import follows.
        next_node = _node_after_import_block(children, imports[-1])
        if next_node is not None and next_node.kind not in _IMPORT_KINDS:
            gap = ctx.source[block_end:next_node.start]
            if gap.count("\n") < 2:
                fix_end = next_node.start
                replacement = sorted_text + "\n\n"

        original = ctx.source[block_start:fix_end]
        if replacement == original:
            return

        ctx.report(
            imports[0],
            fix=Fix(
                start=block_start,
                end=fix_end,
                replacement=replacement,
                safety="safe",
            ),
        )


def _top_level_import_block(children: list["Node"]) -> list["Node"]:
    """First contiguous module-level import run after preamble."""
    i = 0
    while i < len(children) and children[i].kind in _PREAMBLE_KINDS:
        i += 1
    imports: list["Node"] = []
    while i < len(children):
        kind = children[i].kind
        if kind in _IMPORT_KINDS:
            imports.append(children[i])
            i += 1
            continue
        if kind == "comment" and imports:
            # Skip mid-block comments; they fall inside the fix span.
            i += 1
            continue
        break
    return imports


def _node_after_import_block(
    children: list["Node"], last_import: "Node"
) -> "Node" | None:
    """Return the first module child after ``last_import``, if any."""
    for i, child in enumerate(children):
        if child is last_import or (
            child.start == last_import.start and child.end == last_import.end
        ):
            if i + 1 < len(children):
                return children[i + 1]
            return None
    return None


def _render_sorted(
    ctx: RuleContext,
    imports: list["Node"],
    known_first: list[str],
    cbp_prefix: str,
) -> str:
    buckets: list[list["Node"]] = [[], [], [], []]
    for node in imports:
        buckets[_classify(ctx, node, known_first, cbp_prefix)].append(node)

    parts: list[str] = []
    for section in buckets:
        if not section:
            continue
        ordered = sorted(section, key=lambda n: _sort_key(ctx, n))
        parts.append("\n".join(n.text() for n in ordered))
    return "\n\n".join(parts)


def _classify(
    ctx: RuleContext,
    node: "Node",
    known_first: list[str],
    cbp_prefix: str,
) -> int:
    name, is_relative = _top_level_module(ctx, node)
    if is_relative:
        return _SECTION_FIRST
    if name is None:
        return _SECTION_THIRD
    if name in _STDLIB:
        return _SECTION_STDLIB
    if cbp_prefix and name.startswith(cbp_prefix):
        return _SECTION_CBP
    if name in known_first:
        return _SECTION_FIRST
    return _SECTION_THIRD


def _sort_key(ctx: RuleContext, node: "Node") -> tuple[int, str, str]:
    # Plain ``import`` before ``from … import``.
    kind_rank = 0 if node.kind == "import_statement" else 1
    path = _module_path_for_sort(ctx, node)
    return (kind_rank, path.casefold(), node.text().casefold())


def _top_level_module(ctx: RuleContext, node: "Node") -> tuple[str | None, bool]:
    """Return ``(top_level_name, is_relative)`` for an import statement."""
    if node.kind == "import_statement":
        for child in ctx.children(node):
            extracted = _name_from_import_child(ctx, child)
            if extracted is not None:
                return extracted.split(".", 1)[0], False
        return None, False

    if node.kind == "import_from_statement":
        for child in ctx.children(node):
            if child.kind == "relative_import":
                return None, True
            if child.kind == "dotted_name":
                return child.text().split(".", 1)[0], False
        return None, False

    return None, False


def _module_path_for_sort(ctx: RuleContext, node: "Node") -> str:
    if node.kind == "import_statement":
        names: list[str] = []
        for child in ctx.children(node):
            extracted = _name_from_import_child(ctx, child)
            if extracted is not None:
                names.append(extracted)
        return ",".join(names) if names else node.text()

    if node.kind == "import_from_statement":
        for child in ctx.children(node):
            if child.kind == "relative_import":
                return child.text()
            if child.kind == "dotted_name":
                return child.text()
    return node.text()


def _name_from_import_child(ctx: RuleContext, child: "Node") -> str | None:
    if child.kind == "dotted_name":
        return child.text()
    if child.kind == "aliased_import":
        for sub in ctx.children(child):
            if sub.kind == "dotted_name":
                return sub.text()
            if sub.kind == "identifier":
                return sub.text()
    return None
