from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from plintus.config import Config
from plintus.document import parse_file
from plintus.engine import (
    apply_diagnostics_fixes,
    lint_source,
    load_rules,
    rules_hash,
)
from plintus.rules.string_utils import requote
from plintus import _core

FIXTURES = Path(__file__).parent / "fixtures"


def _cfg(**kwargs) -> Config:
    base = Config(cache=False, workers=1)
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_parse_preserves_quotes():
    doc, _ = parse_file("x.py", 'x = {"a": \'b\'}\n')
    strings = [n.text() for n in doc.select(["string"])]
    assert '"a"' in strings
    assert "'b'" in strings
    doc.close()


def test_q001_q002_and_b001_strong():
    """Strengthened: exact count + per-diagnostic line/col/severity/fix."""
    src = (FIXTURES / "quotes_and_banned.py").read_text(encoding="utf-8")
    cfg = _cfg(select=["Q001", "Q002", "BAN001"])
    diags = lint_source("quotes_and_banned.py", src, load_rules(cfg), cfg)
    assert len(diags) == 5
    by_id = {}
    for d in diags:
        by_id.setdefault(d.rule_id, []).append(d)
    assert sorted(by_id) == ["BAN001", "Q001", "Q002"]
    # Q001: two dict strings at line 1
    q1 = sorted(by_id["Q001"], key=lambda d: d.col)
    assert [(d.line, d.col, d.severity.value) for d in q1] == [
        (1, 6, "warning"),
        (1, 13, "warning"),
    ]
    assert q1[0].fix is not None and q1[0].fix.replacement == "'key'"
    assert q1[1].fix is not None and q1[1].fix.replacement == "'value'"
    # Q002: print + raise messages
    q2 = sorted(by_id["Q002"], key=lambda d: d.line)
    assert [(d.line, d.severity.value) for d in q2] == [(2, "warning"), (3, "warning")]
    assert q2[0].fix is not None and q2[0].fix.replacement == '"msg"'
    assert q2[1].fix is not None and q2[1].fix.replacement == '"boom"'
    # BAN001: eval, error severity, no fix
    b1 = by_id["BAN001"][0]
    assert b1.line == 4 and b1.severity.value == "error" and b1.fix is None
    assert "eval" in b1.message


def test_safe_requote_and_fix_idempotent():
    src = 'd = {"a": "b"}\nprint(\'hi\')\n'
    cfg = _cfg(select=["Q001", "Q002"])
    rules = load_rules(cfg)
    diags = lint_source("t.py", src, rules, cfg)
    new_src, remaining = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == "d = {'a': 'b'}\nprint(\"hi\")\n"
    # second pass should be clean (no diagnostics, no remaining)
    diags2 = lint_source("t.py", new_src, rules, cfg)
    new2, rem2 = apply_diagnostics_fixes(new_src, diags2, unsafe=False)
    assert new2 == new_src
    assert diags2 == [] and rem2 == []


def test_requote_rejects_ambiguous():
    result = requote('"plain"', "single")
    assert result == ("'plain'", True)
    # contains unescaped single quote — cannot safely switch to single quotes
    assert requote('''"it's"''', "single") is None


def test_unicode_offsets_reports_diagnostics():
    src = (FIXTURES / "unicode.py").read_text(encoding="utf-8")
    raw = src.encode("utf-8")
    cfg = _cfg(select=["Q001", "Q002"])
    diags = lint_source("unicode.py", src, load_rules(cfg), cfg)
    assert len(diags) >= 2, "expected diagnostics for unicode fixture"
    for d in diags:
        assert 0 <= d.start <= d.end <= len(raw)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    new_src.encode("utf-8")  # must not raise
    assert "привет" in new_src


def test_invalid_syntax_still_parses_and_lints():
    src = (FIXTURES / "invalid_syntax.py").read_text(encoding="utf-8")
    doc, _ = parse_file("bad.py", src)
    assert doc.node_count >= 1
    doc.close()
    # linting broken files must not crash; tree-sitter error recovery yields
    # whatever nodes it can. No specific diagnostic expectation here.
    cfg = _cfg(select=["Q001"])
    lint_source("bad.py", src, load_rules(cfg), cfg)


def test_call_arg_order_strong():
    src = (FIXTURES / "call_order.py").read_text(encoding="utf-8")
    cfg = _cfg(
        select=["ORD001"],
        call_arg_order={"client.request": ["method", "url", "timeout"]},
    )
    diags = lint_source("call_order.py", src, load_rules(cfg), cfg)
    ord_diags = [d for d in diags if d.rule_id == "ORD001"]
    assert len(ord_diags) == 1
    d = ord_diags[0]
    assert d.line == 3
    assert "client.request" in d.message
    assert "method, url, timeout" in d.message


def test_call_arg_order_correct_passes():
    src = "from app import client\nclient.request(method='GET', url='/', timeout=1)\n"
    cfg = _cfg(
        select=["ORD001"],
        call_arg_order={"client.request": ["method", "url", "timeout"]},
    )
    diags = lint_source("ok.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "ORD001" for d in diags)


def test_require_decorator_strong():
    src = (FIXTURES / "decorators.py").read_text(encoding="utf-8")
    cfg = _cfg(
        select=["DEC001"],
        require_decorators={"handle_event": ["login_required"]},
    )
    diags = lint_source("decorators.py", src, load_rules(cfg), cfg)
    dec = [d for d in diags if d.rule_id == "DEC001"]
    assert len(dec) == 1
    assert dec[0].line == 1
    assert "handle_event" in dec[0].message
    assert "login_required" in dec[0].message
    assert not any("ok_view" in d.message for d in diags)


def test_require_decorator_passes_when_decorated():
    """DEC001 must NOT fire on a decorated function whose decorator is required.

    Regression for the P1 bug where decorators were looked up among
    function_definition children instead of on the decorated_definition parent.
    """
    src = (
        "def login_required(f):\n"
        "    return f\n"
        "\n"
        "@login_required\n"
        "def ok_view():\n"
        "    return 1\n"
    )
    cfg = _cfg(
        select=["DEC001"],
        require_decorators={"ok_view": ["login_required"]},
    )
    diags = lint_source("ok.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "DEC001" for d in diags)


def test_require_decorator_dotted_and_parameterized():
    """Dotted (@pkg.deco) and parameterized (@deco(...)) decorators resolve."""
    src = (
        "import functools\n"
        "\n"
        "@functools.wraps(lambda f: f)\n"
        "def view():\n"
        "    pass\n"
        "\n"
        "@pkg.login_required\n"
        "def other():\n"
        "    pass\n"
    )
    cfg = _cfg(
        select=["DEC001"],
        require_decorators={
            "view": ["functools.wraps"],
            "other": ["pkg.login_required"],
        },
    )
    diags = lint_source("d.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "DEC001" for d in diags)


def test_cache_hit_and_invalidation(tmp_path: Path):
    """Real cache test: hit on identical input, miss on rule-body change.

    Uses tmp_path for isolation (no leaked .plintus_cache_test dir).
    """
    cache_dir = tmp_path / "cache"
    src = "print('ok')\n"
    cfg = Config(cache=True, cache_dir=str(cache_dir), workers=1, select=["Q002"])
    rules = load_rules(cfg)
    d1 = lint_source("c.py", src, rules, cfg, use_cache=True)
    d2 = lint_source("c.py", src, rules, cfg, use_cache=True)
    assert [x.to_dict() for x in d1] == [x.to_dict() for x in d2]
    assert len(d1) == 1 and d1[0].rule_id == "Q002"

    # Changing rule implementation body (without bumping api_version) must
    # invalidate the cache via rules_hash.
    from plintus.api import Rule as _Rule, RuleContext, Severity

    class AltQ002(_Rule):
        id = "Q002"
        message = "DIFFERENT message"
        severity = Severity.WARNING
        targets = ("string",)
        api_version = "1"

        def check(self, ctx: RuleContext) -> None:
            for node in ctx.nodes:
                ctx.report(node, self.message)

    alt_rules = [AltQ002()]
    # rules_hash differs from the builtin Q002 hash (different check body)
    assert rules_hash(alt_rules) != rules_hash(rules)
    d3 = lint_source("c.py", src, alt_rules, cfg, use_cache=True)
    assert any(d.message == "DIFFERENT message" for d in d3)


def test_wps_factory_rules_have_distinct_hashes():
    """Factory-built WPS rules must not share one hash via the wrapper check()."""
    from plintus.rules.wps._factory import make_rule

    def checker_a(ctx):
        ctx.report(ctx.nodes[0] if ctx.nodes else None, "a")

    def checker_b(ctx):
        for node in ctx.nodes:
            ctx.report(node, "b")

    ra = make_rule("WPS999A", "a", (), checker_a)
    rb = make_rule("WPS999B", "b", (), checker_b)
    # Same wrapper shape, different closed-over checkers → different hashes
    assert rules_hash([ra]) != rules_hash([rb])


def test_snapshot_diagnostics_json():
    """Golden snapshot. Fails if the snapshot file is missing (no auto-create).

    To regenerate: UPDATE_SNAPSHOTS=1 python -m pytest tests/test_lint.py::test_snapshot_diagnostics_json
    """
    src = (FIXTURES / "quotes_and_banned.py").read_text(encoding="utf-8")
    cfg = _cfg(select=["Q001", "Q002", "BAN001"])
    diags = lint_source("quotes_and_banned.py", src, load_rules(cfg), cfg)
    payload = [
        {
            "rule_id": d.rule_id,
            "message": d.message,
            "severity": d.severity.value,
            "line": d.line,
            "col": d.col,
            "start": d.start,
            "end": d.end,
            "fix": None
            if d.fix is None
            else {
                "start": d.fix.start,
                "end": d.fix.end,
                "replacement": d.fix.replacement,
                "safety": d.fix.safety,
            },
        }
        for d in diags
    ]
    expected = FIXTURES / "quotes_and_banned.snapshot.json"
    if os.environ.get("UPDATE_SNAPSHOTS"):
        expected.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    assert expected.is_file(), (
        f"snapshot missing: {expected}. Run with UPDATE_SNAPSHOTS=1 to create."
    )
    assert json.loads(expected.read_text(encoding="utf-8")) == payload


def test_api_version_matches():
    assert _core.api_version() == "1"


def test_q001_skips_json_response_fstring_with_inner_quotes():
    """Dict value f\"...'{x}'...\" cannot safely switch to single quotes."""
    src = (
        "from aiohttp import web\n"
        "async def delete_client(self, client_id: str):\n"
        "    return web.json_response("
        "{'error': f\"Client '{client_id}' not found\"}, status=404)\n"
    )
    cfg = _cfg(select=["Q001", "Q002"])
    diags = lint_source("view.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "Q001" for d in diags)
    # f-string is inside a dict → Q002 does not own it
    assert not any(d.rule_id == "Q002" for d in diags)


def test_q001_still_flags_plain_dict_double_quotes():
    src = 'd = {"a": "b"}\n'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("d.py", src, load_rules(cfg), cfg)
    assert any(d.rule_id == "Q001" for d in diags)


def test_fix_safety_validation():
    from plintus.api import Fix

    with pytest.raises(ValueError):
        Fix(0, 1, "x", safety="typo")
    # valid values
    Fix(0, 1, "x", safety="safe")
    Fix(0, 1, "x", safety="unsafe")
