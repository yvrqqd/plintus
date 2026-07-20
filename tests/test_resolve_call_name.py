"""Tests for resolve_call_name / _expr_name edge cases (improvement-plan §11/§28)."""

from __future__ import annotations

from plintus.api import resolve_call_name
from plintus.document import parse_file


def _outer_call_name(src: str) -> str | None:
    """Resolve the outermost call in a one-statement source snippet."""
    doc, _ = parse_file("t.py", src if src.endswith("\n") else src + "\n")
    try:
        calls = doc.select(["call"])
        assert calls, f"no call nodes in {src!r}"
        # Outermost call is the one with the largest span covering the statement.
        outer = max(calls, key=lambda n: n.end - n.start)
        return resolve_call_name(doc, outer)
    finally:
        doc.close()


def test_resolve_plain_identifier_call():
    assert _outer_call_name('eval("x")') == "eval"


def test_resolve_attribute_call():
    assert _outer_call_name("obj.method()") == "obj.method"
    assert _outer_call_name("a.b.c()") == "a.b.c"


def test_resolve_parenthesized_callee():
    """Parentheses around the callee must unwrap: (eval)(\"x\") → eval."""
    assert _outer_call_name('(eval)("x")') == "eval"


def test_resolve_call_receiver_attribute():
    """Call-as-receiver: descend into the call's function, keep the attr.

    Expected: ``(foo()).bar()`` resolves to ``foo.bar`` (not just ``bar``).
    Likewise ``df.groupby(\"x\").sum()`` → ``df.groupby.sum``.
    """
    assert _outer_call_name("(foo()).bar()") == "foo.bar"
    assert _outer_call_name('df.groupby("x").sum()') == "df.groupby.sum"
