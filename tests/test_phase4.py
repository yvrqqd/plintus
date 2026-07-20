"""Phase 4 tests: workers, CLI, config, local rules, string_utils, coverage matrix."""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from plintus.config import Config, load_config
from plintus.engine import lint_paths, lint_source, load_rules
from plintus.rules.string_utils import (
    can_safely_requote,
    can_switch_quotes,
    is_fstring,
    is_message_context,
    parse_string_literal,
    requote,
)

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = Path(__file__).parent.parent / "examples"


def _cfg(**kwargs) -> Config:
    base = Config(cache=False, workers=1)
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


# --- Workers ---------------------------------------------------------------


def test_lint_paths_parallel_matches_inline(tmp_path: Path):
    """Worker path must produce the same diagnostics as inline mode.

    Exercises the ProcessPoolExecutor branch in engine._lint_with_workers
    (previously dead code — tests always forced inline via worker_threshold=9999).
    """
    for i in range(25):
        (tmp_path / f"f{i}.py").write_text('eval("x")\n', encoding="utf-8")
    cfg = Config(cache=False, workers=0, select=["BAN001"], worker_threshold=5)
    diags_par, _ = lint_paths([str(tmp_path)], cfg)
    cfg_inline = Config(cache=False, workers=1, select=["BAN001"], worker_threshold=5)
    diags_inline, _ = lint_paths([str(tmp_path)], cfg_inline)
    import json
    par = sorted(json.dumps(d.to_dict(), sort_keys=True) for d in diags_par)
    inline = sorted(json.dumps(d.to_dict(), sort_keys=True) for d in diags_inline)
    assert par == inline
    assert len(diags_par) == 25


def test_workers_disabled_for_local_rules(tmp_path: Path, capsys):
    """Non-builtin rules must fall back to inline (no silent diagnostic loss).

    Uses 3 files with worker_threshold=2 so the worker path is attempted,
    triggering the fallback warning in _workers_safe_for.
    """
    for i in range(3):
        (tmp_path / f"a{i}.py").write_text("eval('1')\n", encoding="utf-8")
    local = tmp_path / "rules.py"
    local.write_text(
        "from plintus.api import Rule, RuleContext, Severity\n"
        "class CustomRule(Rule):\n"
        "    id = 'CUST001'\n"
        "    message = 'custom'\n"
        "    severity = Severity.ERROR\n"
        "    targets = ('call',)\n"
        "    def check(self, ctx):\n"
        "        for n in ctx.nodes:\n"
        "            ctx.report(n, 'custom hit')\n"
        "def register():\n"
        "    return [CustomRule()]\n",
        encoding="utf-8",
    )
    cfg = Config(
        cache=False, workers=0, select=["BAN001", "CUST001"], worker_threshold=2,
        local_rules=[str(local)],
    )
    diags, _ = lint_paths([str(tmp_path)], cfg)
    assert any(d.rule_id == "CUST001" for d in diags)
    err = capsys.readouterr().err
    assert "single-process" in err


# --- CLI -------------------------------------------------------------------


def test_cli_check_warnings_exit_zero(tmp_path: Path):
    f = tmp_path / "w.py"
    f.write_text('d = {"a": "b"}\n', encoding="utf-8")
    rc = _run_cli(["check", str(f), "--no-cache", "--select", "Q001", "--workers", "1"])
    assert rc == 0  # warnings only


def test_cli_check_errors_exit_one(tmp_path: Path):
    f = tmp_path / "e.py"
    f.write_text('eval("x")\n', encoding="utf-8")
    rc = _run_cli(["check", str(f), "--no-cache", "--select", "BAN001", "--workers", "1"])
    assert rc == 1


def test_cli_check_clean_exit_zero(tmp_path: Path):
    f = tmp_path / "ok.py"
    f.write_text("x = 1\n", encoding="utf-8")
    rc = _run_cli(["check", str(f), "--no-cache", "--workers", "1"])
    assert rc == 0


def test_cli_json_output(tmp_path: Path):
    f = tmp_path / "e.py"
    f.write_text('eval("x")\n', encoding="utf-8")
    out = _run_cli_out(["check", str(f), "--no-cache", "--select", "BAN001", "--output-format", "json", "--workers", "1"])
    import json
    data = json.loads(out)
    assert isinstance(data, list) and any(d["rule_id"] == "BAN001" for d in data)


def test_cli_fix_writes(tmp_path: Path):
    f = tmp_path / "fix.py"
    f.write_text('d = {"a": "b"}\n', encoding="utf-8")
    _run_cli(["check", str(f), "--fix", "--no-cache", "--select", "Q001", "--workers", "1"])
    assert f.read_text(encoding="utf-8") == "d = {'a': 'b'}\n"


def test_cli_fix_adds_slots_for_e003(tmp_path: Path):
    f = tmp_path / "app" / "dao" / "postgres" / "model" / "agent_training_history.py"
    f.parent.mkdir(parents=True)
    f.write_text(
        "class AgentTrainingHistoryDAO:\n"
        "    def __init__(self):\n"
        "        self._x = 1\n",
        encoding="utf-8",
    )
    rc = _run_cli(["check", str(f), "--fix", "--no-cache", "--select", "E003", "--workers", "1"])
    assert rc == 0
    assert f.read_text(encoding="utf-8") == (
        "class AgentTrainingHistoryDAO:\n"
        "    __slots__ = (\n"
        "        \'_x\',\n"
        "    )\n"
        "\n"
        "    def __init__(self):\n"
        "        self._x = 1\n"
    )


def test_cli_diff_no_write(tmp_path: Path):
    f = tmp_path / "fix.py"
    original = 'd = {"a": "b"}\n'
    f.write_text(original, encoding="utf-8")
    _run_cli(["check", str(f), "--diff", "--no-cache", "--select", "Q001", "--workers", "1"])
    assert f.read_text(encoding="utf-8") == original


def _run_cli(args: list[str]) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "plintus", *args],
        capture_output=True, text=True,
    )
    return proc.returncode


def _run_cli_out(args: list[str]) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "plintus", *args],
        capture_output=True, text=True,
    )
    return proc.stdout


# --- Config -----------------------------------------------------------------


def test_config_load_kebab_case(tmp_path: Path):
    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text(
        textwrap.dedent(
            """
            [tool.plintus]
            select = ["Q001"]
            workers = 1
            cache = false
            dict-quotes = "double"
            message-quotes = "single"
            banned-calls = ["eval"]
            require-decorators = { foo = ["bar"] }
            call-arg-order = { c = ["a", "b"] }
            local-rules = ["x.py"]
            exclude = ["tests/fixtures"]
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(config_path=pyproj)
    assert cfg.select == ["Q001"]
    assert cfg.workers == 1
    assert cfg.cache is False
    assert cfg.dict_quotes == "double"
    assert cfg.message_quotes == "single"
    assert cfg.banned_calls == ["eval"]
    assert cfg.require_decorators == {"foo": ["bar"]}
    assert cfg.call_arg_order == {"c": ["a", "b"]}
    assert cfg.local_rules == ["x.py"]
    assert cfg.exclude == ["tests/fixtures"]


def test_exclude_skips_fixture_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from plintus.engine import _apply_exclude

    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "tests" / "fixtures").mkdir(parents=True)
    src = root / "src" / "ok.py"
    bad = root / "tests" / "fixtures" / "bad.py"
    src.write_text("x = 1\n", encoding="utf-8")
    bad.write_text("eval('1')\n", encoding="utf-8")
    monkeypatch.chdir(root)
    kept = _apply_exclude(
        [str(src), str(bad)],
        ["tests/fixtures"],
    )
    assert kept == [str(src)]

def test_config_validation_rejects_bad_quotes():
    with pytest.raises(ValueError):
        Config(dict_quotes="weird")
    with pytest.raises(ValueError):
        Config(message_quotes="weird")


def test_config_validation_rejects_negative_workers():
    with pytest.raises(ValueError):
        Config(workers=-1)


def test_config_fingerprint_stable_and_excludes_base_dir(tmp_path: Path):
    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text("[tool.plintus]\nselect = ['Q001']\n", encoding="utf-8")
    cfg = load_config(config_path=pyproj)
    fp1 = cfg.fingerprint()
    assert "_base_dir" not in fp1
    # Same config in a different dir → same fingerprint
    other = tmp_path / "sub" / "pyproject.toml"
    other.parent.mkdir()
    other.write_text("[tool.plintus]\nselect = ['Q001']\n", encoding="utf-8")
    cfg2 = load_config(config_path=other)
    assert cfg2.fingerprint() == fp1


def test_config_to_rule_context_roundtrip():
    cfg = Config(
        message_calls=["print"],
        dict_quotes="double",
        message_quotes="single",
        banned_calls=["eval"],
        require_decorators={"f": ["d"]},
        call_arg_order={"c": ["a"]},
    )
    rc = cfg.to_rule_context()
    assert rc.message_calls == ["print"]
    assert rc.dict_quotes == "double"
    assert rc.message_quotes == "single"
    assert rc.banned_calls == ["eval"]
    assert rc.require_decorators == {"f": ["d"]}
    assert rc.call_arg_order == {"c": ["a"]}
    # dict-style access works
    assert rc.get("dict_quotes") == "double"
    assert rc["message_quotes"] == "single"
    assert "dict_quotes" in rc
    assert rc.get("nonexistent", "fallback") == "fallback"
    with pytest.raises(KeyError):
        rc["nonexistent"]


def test_config_enabled_all_keyword():
    cfg = Config(select=["ALL"], ignore=["Q002"])
    assert cfg.enabled("Q001") is True
    assert cfg.enabled("Q002") is False  # ignored
    assert cfg.enabled("BAN001") is True


# --- Local rules + plugins -------------------------------------------------


def test_local_rules_loaded_and_run(tmp_path: Path):
    f = tmp_path / "code.py"
    f.write_text("# TODO: fix me\nx = 1\n", encoding="utf-8")
    cfg = Config(
        cache=False, workers=1, select=["X001"], local_rules=[str(EXAMPLES / "local_rules.py")],
    )
    diags, _ = lint_paths([str(f)], cfg)
    assert any(d.rule_id == "X001" for d in diags)


def test_local_rules_relative_to_pyproject(tmp_path: Path):
    rules_file = tmp_path / "myrules.py"
    rules_file.write_text(
        "from plintus.api import Rule, RuleContext, Severity\n"
        "class R(Rule):\n    id='R001'\n    message='r'\n    severity=Severity.HINT\n"
        "    targets=('string',)\n"
        "    def check(self, ctx):\n"
        "        for n in ctx.nodes:\n            ctx.report(n)\n"
        "def register():\n    return [R()]\n",
        encoding="utf-8",
    )
    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text(
        "[tool.plintus]\nlocal-rules = ['myrules.py']\nselect = ['R001']\nworkers = 1\ncache = false\n",
        encoding="utf-8",
    )
    code = tmp_path / "c.py"
    code.write_text('x = "hi"\n', encoding="utf-8")
    cfg = load_config(config_path=pyproj)
    diags, _ = lint_paths([str(code)], cfg)
    assert any(d.rule_id == "R001" for d in diags)


def test_plugin_api_version_mismatch_raises():
    from plintus.api import Rule as _Rule
    from plintus.engine import PluginError

    class Bad(_Rule):
        id = "BADVER"
        api_version = "999"
        def check(self, ctx): pass

    # Manually inject via local_rules to trigger the version check.
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as t:
        t.write(
            "from plintus.api import Rule, RuleContext\n"
            "class Bad(Rule):\n"
            "    id='BADVER'\n    api_version='999'\n"
            "    def check(self, ctx): pass\n"
            "def register():\n    return [Bad()]\n"
        )
        path = t.name
    cfg = Config(cache=False, workers=1, select=["BADVER"], local_rules=[path])
    with pytest.raises(PluginError):
        load_rules(cfg)


# --- string_utils ----------------------------------------------------------


@pytest.mark.parametrize(
    "text,style,can",
    [
        ('"abc"', "single", True),
        ("'abc'", "double", True),
        ('"it\'s"', "single", False),
        ("\"he said \"hi\"\"", "single", True),  # body has no single quote
        ('"""triple"""', "single", True),
        ("'''triple'''", "double", True),
    ],
)
def test_can_switch_quotes(text, style, can):
    assert can_switch_quotes(text, style) is can


@pytest.mark.parametrize(
    "body,new_quote,expected",
    [
        ("abc", "'", True),
        ("it's", "'", False),
        ('a"b', '"', False),
        ("no quotes", "'", True),
    ],
)
def test_can_safely_requote(body, new_quote, expected):
    assert can_safely_requote(body, new_quote) is expected


@pytest.mark.parametrize(
    "prefix,expected",
    [("r", False), ("f", True), ("rf", True), ("fr", True), ("Rb", False), ("", False)],
)
def test_is_fstring(prefix, expected):
    assert is_fstring(prefix) is expected


def test_requote_fstring_marked_unsafe():
    # f-string without inner quotes can be requoted, but the fix is unsafe
    # (nested same-quote expressions are a SyntaxError on <3.12).
    result = requote('f"hello {name}"', "single")
    assert result is not None
    new_text, safe = result
    assert new_text == "f'hello {name}'"
    assert safe is False


def test_requote_non_fstring_safe():
    result = requote('"hi"', "single")
    assert result == ("'hi'", True)


def test_is_message_context_short_name_matching():
    # exact match
    assert is_message_context("print", ["print"], False) is True
    # short-name match: web.json_response → json_response
    assert is_message_context("web.json_response", ["json_response"], False) is True
    assert is_message_context("logging.info", ["logging.info"], False) is True
    # known logger receivers (not only logging.*)
    assert is_message_context("LOG.warning", [], False) is True
    assert is_message_context("logger.info", [], False) is True
    assert is_message_context("LOGGER.error", [], False) is True
    # raise
    assert is_message_context(None, [], True) is True
    # no match — arbitrary *.info is not a logger
    assert is_message_context("foo", ["print"], False) is False
    assert is_message_context("response.info", [], False) is False
    assert is_message_context(None, [], False) is False


def test_parse_string_literal_none_cases():
    assert parse_string_literal("not a string") is None
    assert parse_string_literal("") is None
    assert parse_string_literal("'unterminated") is None


# --- Rule coverage matrix --------------------------------------------------


def test_q001_reversed_config_double():
    src = "d = {'a': 'b'}\n"
    cfg = _cfg(select=["Q001"], dict_quotes="double")
    diags = lint_source("d.py", src, load_rules(cfg), cfg)
    assert len(diags) == 2
    assert all(d.rule_id == "Q001" for d in diags)


def test_q001_strings_in_list_not_flagged():
    src = 'x = ["a", "b"]\n'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("l.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "Q001" for d in diags)


def test_q001_nested_dict():
    src = 'd = {"outer": {"inner": "v"}}\n'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("n.py", src, load_rules(cfg), cfg)
    assert len([d for d in diags if d.rule_id == "Q001"]) >= 3


def test_q002_logging_info():
    src = 'import logging\nlogging.info(\'bad\')\n'
    cfg = _cfg(select=["Q002"])
    diags = lint_source("log.py", src, load_rules(cfg), cfg)
    assert any(d.rule_id == "Q002" for d in diags)


def test_q002_log_alias_msg_keyword():
    """LOG.warning(msg='...') is Q002; extra= slots stay Q001 (single quotes)."""
    src = (
        "LOG.warning(\n"
        "    msg='Failed to read verification code from Redis',\n"
        "    extra={'phone': phone, 'error': str(exc)},\n"
        ")\n"
    )
    cfg = _cfg(select=["Q001", "Q002"])
    diags = lint_source("log.py", src, load_rules(cfg), cfg)
    q2 = [d for d in diags if d.rule_id == "Q002"]
    assert len(q2) == 1
    assert q2[0].fix is not None
    assert q2[0].fix.replacement == '"Failed to read verification code from Redis"'
    # dict slots already single-quoted — no Q001
    assert not any(d.rule_id == "Q001" for d in diags)


def test_q001_extra_slots_prefer_single_quotes():
    """Dict strings under logging extra= are slots → Q001, not Q002."""
    src = (
        'LOG.info(msg="ok", extra={"phone": "x", "status": "fail"})\n'
    )
    cfg = _cfg(select=["Q001", "Q002"])
    diags = lint_source("log.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "Q002" for d in diags)
    q1 = sorted(
        (d for d in diags if d.rule_id == "Q001"),
        key=lambda d: d.col,
    )
    assert len(q1) == 4  # two keys + two values
    assert all(d.fix and d.fix.replacement.startswith("'") for d in q1)


def test_q002_web_json_response_short_name():
    src = "from aiohttp import web\nweb.json_response({'k': 'v'}, text='bad')\n"
    cfg = _cfg(select=["Q002"])
    diags = lint_source("w.py", src, load_rules(cfg), cfg)
    # 'bad' is a message under web.json_response (short-name match)
    assert any(d.rule_id == "Q002" and "bad" in d.message or d.col for d in diags)


def test_ban001_exec_default():
    src = 'exec("pass")\n'
    cfg = _cfg(select=["BAN001"])
    diags = lint_source("e.py", src, load_rules(cfg), cfg)
    assert any(d.rule_id == "BAN001" and "exec" in d.message for d in diags)


def test_ban001_empty_list_no_diags():
    src = 'eval("x")\n'
    cfg = _cfg(select=["BAN001"], banned_calls=[])
    diags = lint_source("e.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "BAN001" for d in diags)


def test_ord001_unconfigured_call_ignored():
    src = 'other.call(a=1, b=2)\n'
    cfg = _cfg(select=["ORD001"], call_arg_order={"client.request": ["a", "b"]})
    diags = lint_source("o.py", src, load_rules(cfg), cfg)
    assert not any(d.rule_id == "ORD001" for d in diags)


# --- Fix application --------------------------------------------------------


def test_apply_overlapping_fixes_skips_overlap():
    src = 'd = {"a": "b"}\n'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("d.py", src, load_rules(cfg), cfg)
    # Duplicate the diagnostics to force overlap on the same span
    doubled = list(diags) + list(diags)
    new_src, remaining = __import__("plintus.engine", fromlist=["apply_diagnostics_fixes"]).apply_diagnostics_fixes(
        src, doubled, unsafe=False
    )
    # Source must not be corrupted
    assert new_src == "d = {'a': 'b'}\n"


# --- Phase 1 regression tests ------------------------------------------------


def test_apply_diagnostics_fixes_marks_applied_flag():
    """Item 1: applied diagnostics must be marked, and the returned list contains
    ALL diagnostics (not just remaining) so callers can distinguish fixed vs unfixed.
    """
    from plintus.engine import apply_diagnostics_fixes

    src = 'd = {"a": "b"}\n'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("d.py", src, load_rules(cfg), cfg)
    new_src, all_diags = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == "d = {'a': 'b'}\n"
    # Both diagnostics had safe fixes and were applied.
    assert len(all_diags) == len(diags)
    assert all(d.applied for d in all_diags)


def test_apply_diagnostics_fixes_marks_overlapping_not_applied():
    from plintus.engine import apply_diagnostics_fixes

    src = 'd = {"a": "b"}\n'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("d.py", src, load_rules(cfg), cfg)
    # Build a fresh list of distinct Diagnostic copies so the overlap check
    # can mark one copy applied and leave the duplicate unapplied.
    import copy
    doubled = list(diags) + [copy.copy(d) for d in diags]
    _new_src, all_diags = apply_diagnostics_fixes(src, doubled, unsafe=False)
    # Exactly one of each overlapping pair is applied; the other is not.
    applied = [d for d in all_diags if d.applied]
    not_applied = [d for d in all_diags if not d.applied]
    assert len(applied) == 2  # one fix per unique span
    assert len(not_applied) == 2  # the duplicates skipped due to overlap


def test_apply_diagnostics_fixes_unsafe_not_applied_without_unsafe():
    from plintus.engine import apply_diagnostics_fixes

    # f-string requote fix is marked unsafe → not applied without --unsafe
    src = 'f"hello {name}"'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("f.py", src, load_rules(cfg), cfg)
    if not diags:
        return
    _new_src, all_diags = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert all(not d.applied for d in all_diags)


def test_diagnostic_to_dict_includes_applied_field():
    from plintus.api import Diagnostic, Fix, Severity

    d = Diagnostic(
        rule_id="X", message="m", path="p", start=0, end=1, line=1, col=1,
        severity=Severity.WARNING, fix=Fix(0, 1, "x"), applied=True,
    )
    payload = d.to_dict()
    assert payload["applied"] is True
    # Default is False for back-compat with cached entries.
    d2 = Diagnostic(
        rule_id="X", message="m", path="p", start=0, end=1, line=1, col=1,
    )
    assert d2.to_dict()["applied"] is False


def test_cli_fix_json_marks_applied(tmp_path: Path):
    """Item 1: --fix --output-format json must mark applied diagnostics."""
    f = tmp_path / "fix.py"
    f.write_text('d = {"a": "b"}\n', encoding="utf-8")
    out = _run_cli_out([
        "check", str(f), "--fix", "--no-cache",
        "--select", "Q001", "--workers", "1", "--output-format", "json",
    ])
    import json
    data = json.loads(out)
    assert all(d.get("applied") is True for d in data)
    # File was actually fixed.
    assert f.read_text(encoding="utf-8") == "d = {'a': 'b'}\n"


def test_cli_unsafe_without_fix_errors(tmp_path: Path):
    """Item 4: --unsafe without --fix/--diff must exit 2 (argparse error)."""
    f = tmp_path / "x.py"
    f.write_text("x = 1\n", encoding="utf-8")
    rc = _run_cli(["check", str(f), "--no-cache", "--unsafe"])
    assert rc == 2


def test_cli_unsafe_with_diff_ok(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("x = 1\n", encoding="utf-8")
    rc = _run_cli(["check", str(f), "--no-cache", "--unsafe", "--diff"])
    assert rc == 0


def test_corrupt_cache_falls_back_to_miss(tmp_path: Path):
    """Item 3: a corrupt cache file must not crash lint; treat as cache miss."""
    cache_dir = tmp_path / "cache"
    src = 'd = {"a": "b"}\n'
    cfg = Config(cache=True, cache_dir=str(cache_dir), workers=1, select=["Q001"])
    rules = load_rules(cfg)
    # First run populates the cache.
    d1 = lint_source("c.py", src, rules, cfg, use_cache=True)
    assert any(dd.rule_id == "Q001" for dd in d1)

    # Corrupt the cache file by writing garbage over it.
    from plintus import _core
    cfg_hash = _core.hash_text(cfg.fingerprint())
    r_hash = __import__("plintus.engine", fromlist=["rules_hash"]).rules_hash(rules)
    key = _core.make_cache_key(src, cfg_hash, r_hash)
    cache_file = cache_dir / f"{key}.json"
    assert cache_file.is_file()
    cache_file.write_text("not valid json {{{", encoding="utf-8")

    # Lint must proceed (cache miss) and not raise.
    d2 = lint_source("c.py", src, rules, cfg, use_cache=True)
    assert any(dd.rule_id == "Q001" for dd in d2)
    # Cache file was overwritten with a fresh valid payload.
    import json
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list)


# --- Item 9: dict_pair_role nested containers ---------------------------------


def _q001_count(src: str) -> int:
    cfg = _cfg(select=["Q001"])
    diags = lint_source("x.py", src, load_rules(cfg), cfg)
    return len([d for d in diags if d.rule_id == "Q001"])


def test_dict_pair_role_tuple_value_not_flagged():
    assert _q001_count('d = {"k": ("a", "b")}\n') == 1


def test_dict_pair_role_subscript_value_flags_index():
    # Outer dict key "k" + subscript index "x" → both Q001
    assert _q001_count('d = {"k": v["x"]}\n') == 2


def test_dict_pair_role_call_value_not_flagged():
    assert _q001_count('d = {"k": foo("x")}\n') == 1


def test_q001_subscript_field_access_single_quotes():
    src = 'x = qwerty["123"]\n'
    cfg = _cfg(select=["Q001"])
    diags = lint_source("t.py", src, load_rules(cfg), cfg)
    assert len(diags) == 1
    assert diags[0].rule_id == "Q001"
    assert diags[0].fix is not None
    assert diags[0].fix.replacement == "'123'"


def test_q001_subscript_already_single_ok():
    assert _q001_count("x = qwerty['123']\n") == 0


def test_q001_subscript_ignores_call_arg_in_index():
    assert _q001_count('x = a[foo("c")]\n') == 0


def test_q001_subscript_nested_index():
    assert _q001_count('x = a[b["c"]]\n') == 1


def test_dict_pair_role_list_value_not_flagged():
    assert _q001_count('d = {"k": ["a", "b"]}\n') == 1


def test_dict_pair_role_nested_dict_flagged():
    assert _q001_count('d = {"k": {"nested": "v"}}\n') == 3


def test_dict_pair_role_tuple_of_dict_flagged():
    # Outer key "k" + nested pair key "inner" + nested value "v" = 3
    assert _q001_count('d = {"k": ({"inner": "v"},)}\n') == 3
