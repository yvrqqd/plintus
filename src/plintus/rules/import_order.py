"""I001 — CBP import section order with safe autofix.

Sections (blank line between non-empty groups)::

    stdlib
    third-party
    cbp_*          # top-level name startswith configured prefix
    first-party    # known-first-party or relative imports

Within each section::

    import …       # alphabetical by module
    from … import  # alphabetical by module; names sorted too

``from __future__`` stays in the preamble (with copyright / docstring) and is
not reordered. Same-line trailing comments (``# noqa``, ``# type: ignore``)
travel with their import on ``--fix``. Mid-block full-line comments between
imports are not preserved on ``--fix``.

When a rewritten import would exceed ``line-length`` (default 88), ``from``
imports are parenthesized (one name per line) and plain ``import a, b`` is
split into separate ``import`` statements.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _ImportEntry:
    """One top-level import, optionally with a same-line trailing comment."""

    node: "Node"
    trailing_comment: "Node | None" = None

    @property
    def end(self) -> int:
        if self.trailing_comment is not None:
            return self.trailing_comment.end
        return self.node.end


class ImportOrder(Rule):
    """Enforce stdlib → third-party → cbp_* → first-party import sections."""

    id = "I001"
    message = (
        "Imports must be ordered: stdlib, third-party, cbp_*, first-party; "
        "within each section import before from, then alphabetical"
    )
    severity = Severity.WARNING
    targets = ()

    def check(self, ctx: RuleContext) -> None:
        roots = ctx.document.select(("module",))
        if not roots:
            return
        children = ctx.children(roots[0])
        imports = _top_level_import_block(ctx.source, children)
        if len(imports) < 1:
            return

        known_first = list(ctx.config.get("known_first_party", ["app"]))
        cbp_prefix = str(ctx.config.get("cbp_import_prefix", "cbp_"))

        sorted_text = _render_sorted(ctx, imports, known_first, cbp_prefix)
        block_start = imports[0].node.start
        block_end = imports[-1].end
        replacement = sorted_text
        fix_end = block_end

        # Ensure one blank line after the import block when real code follows.
        # Skip same-line trailing comments; they travel with the last import.
        # Full-line comments are not "following code".
        next_node = _node_after_import_block(children, imports[-1])
        if (
            next_node is not None
            and next_node.kind not in _IMPORT_KINDS
            and next_node.kind != "comment"
        ):
            gap = ctx.source[block_end : next_node.start]
            if gap.count("\n") < 2:
                fix_end = next_node.start
                replacement = sorted_text + "\n\n"

        original = ctx.source[block_start:fix_end]
        if replacement == original:
            return

        ctx.report(
            imports[0].node,
            fix=Fix(
                start=block_start,
                end=fix_end,
                replacement=replacement,
                safety="safe",
            ),
        )


def _top_level_import_block(source: str, children: list["Node"]) -> list[_ImportEntry]:
    """First contiguous module-level import run after preamble."""
    i = 0
    while i < len(children) and children[i].kind in _PREAMBLE_KINDS:
        i += 1
    imports: list[_ImportEntry] = []
    while i < len(children):
        kind = children[i].kind
        if kind in _IMPORT_KINDS:
            node = children[i]
            i += 1
            trailing: "Node | None" = None
            if i < len(children) and children[i].kind == "comment":
                if _is_same_line_trailing(source, node, children[i]):
                    trailing = children[i]
                    i += 1
            imports.append(_ImportEntry(node, trailing))
            continue
        if kind == "comment" and imports:
            # Skip mid-block full-line comments; they fall inside the fix span.
            i += 1
            continue
        break
    return imports


def _is_same_line_trailing(source: str, import_node: "Node", comment: "Node") -> bool:
    """True when ``comment`` is an EOL comment on the same line as ``import_node``."""
    gap = source[import_node.end : comment.start]
    return "\n" not in gap and all(c in " \t" for c in gap)


def _node_after_import_block(
    children: list["Node"], last: _ImportEntry
) -> "Node" | None:
    """Return the first module child after ``last`` (and its EOL comment), if any."""
    for i, child in enumerate(children):
        if child is last.node or (
            child.start == last.node.start and child.end == last.node.end
        ):
            j = i + 1
            if (
                last.trailing_comment is not None
                and j < len(children)
                and children[j].kind == "comment"
                and children[j].start == last.trailing_comment.start
                and children[j].end == last.trailing_comment.end
            ):
                j += 1
            if j < len(children):
                return children[j]
            return None
    return None


def _render_sorted(
    ctx: RuleContext,
    imports: list[_ImportEntry],
    known_first: list[str],
    cbp_prefix: str,
) -> str:
    buckets: list[list[_ImportEntry]] = [[], [], [], []]
    for entry in imports:
        buckets[_classify(ctx, entry.node, known_first, cbp_prefix)].append(entry)

    parts: list[str] = []
    for section in buckets:
        if not section:
            continue
        # Format first, then expand plain imports that split into multiple
        # statements so siblings can interleave. Re-sort once so one ``--fix``
        # is final (sort-then-format alone keeps a multi-import as one key).
        units: list[tuple[tuple[int, str, str], str]] = []
        for entry in section:
            formatted = _format_import(ctx, entry)
            if entry.node.kind == "import_statement" and "\n" in formatted:
                for line in formatted.split("\n"):
                    units.append((_plain_import_line_sort_key(line), line))
            else:
                units.append((_sort_key(ctx, entry.node), formatted))
        units.sort(key=lambda u: u[0])
        parts.append("\n".join(text for _, text in units))
    return "\n\n".join(parts)


def _plain_import_line_sort_key(line: str) -> tuple[int, str, str]:
    """Sort key for one formatted ``import …`` line (after a multi-import split)."""
    code = line
    hash_at = line.find("#")
    if hash_at != -1:
        code = line[:hash_at].rstrip()
    rest = code[len("import ") :] if code.startswith("import ") else code
    name = rest.split(" as ", 1)[0].strip()
    return (0, name.casefold(), line.casefold())


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
    # Plain ``import`` before ``from … import``, then alphabetical by module.
    kind_rank = 0 if node.kind == "import_statement" else 1
    path = _module_path_for_sort(ctx, node)
    return (kind_rank, path.casefold(), node.text().casefold())


def _format_import(ctx: RuleContext, entry: _ImportEntry) -> str:
    """Rewrite one import with member names sorted; keep same-line EOL comments."""
    comment_suffix = ""
    if entry.trailing_comment is not None:
        gap = ctx.source[entry.node.end : entry.trailing_comment.start]
        if not gap or "\n" in gap:
            gap = "  "
        comment_suffix = f"{gap}{entry.trailing_comment.text()}"

    # Reserve same-line comment length when deciding whether to wrap.
    reserve = len(comment_suffix)
    formatted = _format_import_statement(ctx, entry.node, reserve=reserve)
    if not comment_suffix:
        return formatted
    # Plain multi-imports may split into several statements; keep the EOL
    # comment on each line. Parenthesized ``from`` keeps the comment on ``)``.
    if "\n" in formatted and entry.node.kind == "import_statement":
        return "\n".join(f"{line}{comment_suffix}" for line in formatted.split("\n"))
    return f"{formatted}{comment_suffix}"


def _line_length(ctx: RuleContext) -> int:
    raw = ctx.config.get("line_length", 88)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 88


def _format_import_statement(
    ctx: RuleContext, node: "Node", *, reserve: int = 0
) -> str:
    """Format an import / import-from node without trailing comments.

    ``reserve`` is extra characters (e.g. a same-line comment) that must fit
    on the single-line form before we wrap or split.
    """
    limit = _line_length(ctx)

    if node.kind == "import_statement":
        import_names = [
            child.text()
            for child in ctx.children(node)
            if child.kind in ("dotted_name", "aliased_import")
        ]
        if not import_names:
            return node.text()
        ordered = sorted(import_names, key=str.casefold)
        single = "import " + ", ".join(ordered)
        if len(single) + reserve <= limit:
            return single
        # Parentheses are invalid for plain ``import``; split into statements.
        return "\n".join(f"import {name}" for name in ordered)

    if node.kind == "import_from_statement":
        module: str | None = None
        from_names: list[str] = []
        seen_import = False
        for child in ctx.children(node):
            if child.kind == "import":
                seen_import = True
                continue
            if not seen_import:
                if child.kind in ("dotted_name", "relative_import"):
                    module = child.text()
                continue
            if child.kind == "wildcard_import":
                return node.text()
            if child.kind in ("dotted_name", "aliased_import"):
                from_names.append(child.text())
        if module is None or not from_names:
            return node.text()
        ordered = sorted(from_names, key=str.casefold)
        single = f"from {module} import " + ", ".join(ordered)
        if len(single) + reserve <= limit:
            return single
        body = "\n".join(f"    {name}," for name in ordered)
        return f"from {module} import (\n{body}\n)"

    return node.text()

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
        if not names:
            return node.text()
        # Match formatted name order so name-sort alone cannot change the
        # section key on a later ``--fix`` pass.
        return ",".join(sorted(names, key=str.casefold))

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
