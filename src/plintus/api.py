"""Versioned public rule API (API_VERSION = 1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterable, Literal, Sequence

if TYPE_CHECKING:
    from plintus.config import RuleContextConfig
    from plintus.document import Document, Node


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


SafetyLevel = Literal["safe", "unsafe"]


@dataclass(frozen=True)
class Fix:
    """Text replacement. Prefer safe fixes that preserve string values.

    ``safety`` is restricted to ``"safe"`` or ``"unsafe"``; any other value
    raises ``ValueError`` at construction time so typos cannot silently bypass
    the unsafe-fix gate in ``apply_diagnostics_fixes``.
    """

    start: int
    end: int
    replacement: str
    safety: SafetyLevel = "safe"

    def __post_init__(self) -> None:
        if self.safety not in ("safe", "unsafe"):
            raise ValueError(
                f"Fix.safety must be 'safe' or 'unsafe', got {self.safety!r}"
            )

    @classmethod
    def replace(
        cls, node: "Node", replacement: str, *, safety: SafetyLevel = "safe"
    ) -> "Fix":
        return cls(start=node.start, end=node.end, replacement=replacement, safety=safety)

    def to_dict(self) -> dict[str, Any]:
        return {
            'start': self.start,
            'end': self.end,
            'replacement': self.replacement,
            'safety': self.safety,
        }


@dataclass
class Diagnostic:
    rule_id: str
    message: str
    path: str
    start: int
    end: int
    line: int
    col: int
    severity: Severity = Severity.ERROR
    fix: Fix | None = None
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            'rule_id': self.rule_id,
            'message': self.message,
            'path': self.path,
            'start': self.start,
            'end': self.end,
            'line': self.line,
            'col': self.col,
            'severity': self.severity.value,
            'applied': self.applied,
        }
        if self.fix is not None:
            d['fix'] = self.fix.to_dict()
        return d


class Rule:
    """Base class for plintus rules.

    Subclasses must set ``id`` and optionally ``targets`` (CST kinds).
    """

    id: str = ""
    message: str = ""
    severity: Severity = Severity.ERROR
    targets: Sequence[str] = ()
    api_version: str = "1"

    def check(self, ctx: "RuleContext") -> None:
        raise NotImplementedError


class RuleContext:
    """Per-file context passed to ``Rule.check``."""

    def __init__(
        self,
        document: "Document",
        nodes: Sequence["Node"],
        rule: Rule,
        config: "RuleContextConfig | dict[str, Any]",
    ) -> None:
        self.document = document
        self.nodes = list(nodes)
        self.rule = rule
        self.config = config
        self._diagnostics: list[Diagnostic] = []

    @property
    def path(self) -> str:
        return self.document.path

    @property
    def source(self) -> str:
        return self.document.source

    def report(
        self,
        node: "Node",
        message: str | None = None,
        *,
        fix: Fix | None = None,
        severity: Severity | None = None,
    ) -> None:
        self._diagnostics.append(
            Diagnostic(
                rule_id=self.rule.id,
                message=message or self.rule.message or self.rule.id,
                path=self.path,
                start=node.start,
                end=node.end,
                line=node.line,
                col=node.col,
                severity=severity or self.rule.severity,
                fix=fix,
            )
        )

    def diagnostics(self) -> list[Diagnostic]:
        return list(self._diagnostics)

    # --- helpers for context-sensitive rules ---

    def ancestors(self, node: "Node") -> list["Node"]:
        return self.document.ancestors(node.id)

    def parent(self, node: "Node") -> "Node" | None:
        return self.document.parent(node.id)

    def children(self, node: "Node") -> list["Node"]:
        return self.document.children(node.id)

    def kind_of(self, node: "Node") -> str:
        return node.kind

    def has_ancestor_kind(self, node: "Node", kinds: Iterable[str]) -> bool:
        wanted = set(kinds)
        return any(a.kind in wanted for a in self.ancestors(node))

    def in_dictionary(self, node: "Node") -> bool:
        return self.has_ancestor_kind(node, ("dictionary", "pair"))

    def in_dict_string(self, node: "Node") -> bool:
        """True if string is a key or value of a dict pair."""
        return self.dict_pair_role(node) is not None

    def dict_pair_role(self, node: "Node") -> str | None:
        """Return ``'key'`` or ``'value'`` if this string sits in a dict pair.

        Strings nested inside a non-pair container (``list``/``tuple``/
        ``subscript``/``call``/``argument_list``/``set``) that lives under a
        pair value are NOT dict strings — they are elements of a collection
        and Q001 must not flag them. Nested ``dictionary`` under a pair value
        is still flagged because its pairs are separate dict strings.
        """
        if node.kind != "string":
            return None
        parent = self.parent(node)
        if parent is not None and parent.kind == "pair":
            kids = [c for c in self.children(parent) if c.kind not in (":", ",")]
            if not kids:
                return None
            if kids[0].id == node.id:
                return "key"
            return "value"
        # String is nested under something other than a direct pair. Walk up;
        # the first ancestor that is a pair OR a non-pair container decides.
        non_pair_containers = (
            "list",
            "tuple",
            "subscript",
            "call",
            "argument_list",
            "set",
        )
        for anc in self.ancestors(node):
            if anc.kind == "pair":
                kids = [c for c in self.children(anc) if c.kind not in (":", ",")]
                if len(kids) < 2:
                    return None
                key_node, value_node = kids[0], kids[-1]
                if node.id == key_node.id:
                    return "key"
                ancs = {a.id for a in self.ancestors(node)}
                if value_node.id in ancs or node.id == value_node.id:
                    return "value"
                return None
            if anc.kind in non_pair_containers:
                # String is an element of a collection under a pair value —
                # not a dict string.
                return None
            # dictionary / other ancestors: keep walking
        return None

    def is_dict_key(self, node: "Node") -> bool:
        return self.dict_pair_role(node) == "key"

    def is_dict_value(self, node: "Node") -> bool:
        return self.dict_pair_role(node) == "value"

    def is_subscript_index_string(self, node: "Node") -> bool:
        """True if string is a subscript index / slice bound (``obj['k']``).

        Does not match strings nested inside calls or other containers under
        the index (``obj[foo("k")]`` is False for ``\"k\"``).
        """
        if node.kind != "string":
            return False
        parent = self.parent(node)
        if parent is None:
            return False
        if parent.kind == "subscript":
            kids = [c for c in self.children(parent) if c.kind not in ("[", "]")]
            # kids[0] is the receiver; remaining children are the index
            return any(c.id == node.id for c in kids[1:])
        if parent.kind == "slice":
            for anc in self.ancestors(node):
                if anc.kind == "subscript":
                    return True
                if anc.kind in (
                    "call",
                    "argument_list",
                    "list",
                    "tuple",
                    "set",
                    "dictionary",
                    "pair",
                ):
                    return False
            return False
        return False

    def enclosing_call_name(self, node: "Node") -> str | None:
        for anc in self.ancestors(node):
            if anc.kind == "call":
                return _call_name(self.document, anc)
        return None

    def is_raise_message(self, node: "Node") -> bool:
        for anc in self.ancestors(node):
            if anc.kind == "raise_statement":
                return True
        return False


def _call_name(document: "Document", call_node: "Node") -> str | None:
    """Best-effort dotted call name from a call node."""
    return resolve_call_name(document, call_node)


def resolve_call_name(document: "Document", call_node: "Node") -> str | None:
    """Public helper: best-effort dotted call name from a ``call`` node.

    Handles ``identifier`` (``foo()``), ``attribute`` (``a.b.c()``),
    parenthesized callees (``(eval)("x")`` → ``eval``), and call receivers on
    attributes (``(foo()).bar()`` → ``foo.bar``, ``df.groupby("x").sum()`` →
    ``df.groupby.sum``). Returns ``None`` if the call target is not a simple
    name expression.
    """
    kids = document.children(call_node.id)
    if not kids:
        return None
    func = kids[0]
    return _expr_name(document, func)


def _paren_inner(document: "Document", node: "Node") -> "Node" | None:
    """Single meaningful child of a ``parenthesized_expression``."""
    meaningful = [c for c in document.children(node.id) if c.kind not in ("(", ")")]
    return meaningful[0] if len(meaningful) == 1 else None


def _expr_name(document: "Document", node: "Node") -> str | None:
    if node.kind == "identifier":
        return node.text()
    if node.kind == "parenthesized_expression":
        inner = _paren_inner(document, node)
        return _expr_name(document, inner) if inner is not None else None
    if node.kind == "call":
        # Nested call receiver: resolve via the call's function child.
        kids = document.children(node.id)
        return _expr_name(document, kids[0]) if kids else None
    if node.kind == "attribute":
        parts: list[str] = []
        cur: "Node" | None = node
        while cur is not None:
            if cur.kind == "identifier":
                parts.append(cur.text())
                break
            if cur.kind == "parenthesized_expression":
                cur = _paren_inner(document, cur)
                continue
            if cur.kind == "call":
                kids = document.children(cur.id)
                cur = kids[0] if kids else None
                continue
            if cur.kind == "attribute":
                children = document.children(cur.id)
                # attribute: object . identifier
                idents = [c for c in children if c.kind == "identifier"]
                if idents:
                    parts.append(idents[-1].text())
                # object may be identifier, attribute, call, or parentheses
                objs = [
                    c
                    for c in children
                    if c.kind
                    in ("identifier", "attribute", "call", "parenthesized_expression")
                ]
                cur = (
                    objs[0]
                    if objs and idents and objs[0].id != idents[-1].id
                    else None
                )
                continue
            break
        parts.reverse()
        return ".".join(parts) if parts else None
    return None
