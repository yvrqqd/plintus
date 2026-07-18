"""Tests for WPS rule pack."""

from __future__ import annotations

from plintus.config import Config, _matches_rule_id
from plintus.engine import lint_source, load_rules
from plintus.rules import register
from plintus.rules.wps.catalog_data import MESSAGES


def _cfg(**kwargs) -> Config:
    base = Config(cache=False, workers=1)
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def _ids(src: str, path: str, select: list[str], *, ignore: list[str] | None = None) -> list[str]:
    cfg = _cfg(select=select, ignore=ignore or [])
    diags = lint_source(path, src, load_rules(cfg), cfg)
    return [d.rule_id for d in diags]


def test_registered_wps_codes_unique_and_known():
    rules = register()
    wps = [r for r in rules if r.id.startswith("WPS")]
    ids = [r.id for r in wps]
    assert len(ids) == len(set(ids))
    assert set(ids) <= set(MESSAGES)
    # Planned stubs must not be registered (false coverage under select=ALL).
    assert "WPS308" not in ids
    assert "WPS440" not in ids
    assert "WPS511" not in ids
    # Implemented / partial codes stay registered.
    assert "WPS421" in ids
    assert "WPS428" in ids
    assert "WPS476" in ids
    assert "WPS451" in ids
    assert "WPS523" in ids


def test_wps_prefix_select_and_ignore():
    assert _matches_rule_id("WPS211", "WPS")
    assert _matches_rule_id("WPS211", "WPS2")
    assert not _matches_rule_id("WPS111", "WPS2")
    cfg = _cfg(select=["WPS"], ignore=["WPS2"])
    rules = load_rules(cfg)
    ids = {r.id for r in rules}
    assert "WPS111" in ids
    assert "WPS421" in ids
    assert "WPS211" not in ids


def test_wps211_too_many_arguments():
    bad = "def f(a, b, c, d, e, f):\n    return a\n"
    good = "def f(a, b):\n    return a\n"
    assert _ids(bad, "t.py", ["WPS211"]) == ["WPS211"]
    assert _ids(good, "t.py", ["WPS211"]) == []


def test_wps212_too_many_returns():
    bad = "def f(x):\n    if x:\n        return 1\n    return 2\n    return 3\n    return 4\n    return 5\n    return 6\n"
    good = "def f(x):\n    return x\n"
    assert "WPS212" in _ids(bad, "t.py", ["WPS212"])
    assert _ids(good, "t.py", ["WPS212"]) == []


def test_wps220_deep_nesting():
    bad = (
        "def f(a):\n"
        "    if a:\n"
        "        if a:\n"
        "            if a:\n"
        "                if a:\n"
        "                    if a:\n"
        "                        if a:\n"
        "                            return 1\n"
    )
    assert "WPS220" in _ids(bad, "t.py", ["WPS220"])


def test_wps421_banned_builtins():
    assert "WPS421" in _ids("print(1)\n", "t.py", ["WPS421"])
    assert "WPS421" in _ids("eval('1')\n", "t.py", ["WPS421"])
    assert "WPS421" in _ids("builtins.print(1)\n", "t.py", ["WPS421"])
    assert _ids("abs(-1)\n", "t.py", ["WPS421"]) == []
    # Method calls must not false-positive on short name.
    assert _ids("obj.print(1)\n", "t.py", ["WPS421"]) == []
    assert _ids("foo.eval('1')\n", "t.py", ["WPS421"]) == []


def test_wps423_not_implemented():
    assert "WPS423" in _ids("raise NotImplemented\n", "t.py", ["WPS423"])
    assert "WPS423" in _ids("raise NotImplemented()\n", "t.py", ["WPS423"])
    assert _ids("raise NotImplementedError\n", "t.py", ["WPS423"]) == []
    # Substring / string text must not false-positive
    assert _ids('raise ValueError("NotImplemented")\n', "t.py", ["WPS423"]) == []
    assert _ids("raise MyNotImplemented\n", "t.py", ["WPS423"]) == []


def test_wps428_skips_docstrings_and_stubs():
    mod = '"""module doc"""\nx = 1\n'
    assert _ids(mod, "t.py", ["WPS428"]) == []
    cls = 'class A:\n    """cls doc"""\n    x = 1\n'
    assert _ids(cls, "t.py", ["WPS428"]) == []
    stub = "class P:\n    def f(self) -> int:\n        ...\n"
    assert _ids(stub, "t.py", ["WPS428"]) == []
    stub_doc = 'def f() -> None:\n    """doc"""\n    ...\n'
    assert _ids(stub_doc, "t.py", ["WPS428"]) == []
    # Real no-op statements still flag.
    assert "WPS428" in _ids("None\n", "t.py", ["WPS428"])
    assert "WPS428" in _ids('"orphan"\n"second"\n', "t.py", ["WPS428"])


def test_wps432_magic_number():
    assert "WPS432" in _ids("x = 42\n", "t.py", ["WPS432"])
    assert _ids("x = 1\n", "t.py", ["WPS432"]) == []


def test_wps111_short_name():
    assert "WPS111" in _ids("a = 1\n", "sample_module.py", ["WPS111"])
    assert _ids("coordinate = 1\n", "sample_module.py", ["WPS111"]) == []


def test_wps347_star_import():
    assert "WPS347" in _ids("from os import *\n", "t.py", ["WPS347"])
    assert _ids("from os import path\n", "t.py", ["WPS347"]) == []


def test_wps476_await_in_for_requires_real_await():
    comment_only = "async def f(items):\n    for x in items:  # await later\n        y = x\n"
    assert _ids(comment_only, "t.py", ["WPS476"]) == []
    real = "async def f(items):\n    for x in items:\n        await x\n"
    assert "WPS476" in _ids(real, "t.py", ["WPS476"])


def test_wps506_useless_lambda():
    assert "WPS506" in _ids("f = lambda x: abs(x)\n", "t.py", ["WPS506"])


def test_wps602_staticmethod():
    src = (
        "class A:\n"
        "    @staticmethod\n"
        "    def f(x):\n"
        "        return x\n"
    )
    assert "WPS602" in _ids(src, "t.py", ["WPS602"])
    wrapper = (
        "class A:\n"
        "    @my_staticmethod_wrapper\n"
        "    def f(x):\n"
        "        return x\n"
    )
    assert _ids(wrapper, "t.py", ["WPS602"]) == []
    dotted = (
        "class A:\n"
        "    @foo.staticmethod\n"
        "    def f(x):\n"
        "        return x\n"
    )
    assert "WPS602" in _ids(dotted, "t.py", ["WPS602"])


def test_wps610_async_magic_methods():
    bad = "class A:\n    async def __init__(self):\n        pass\n"
    good_sync = "class A:\n    def __init__(self):\n        pass\n"
    good_async = "class A:\n    async def fetch(self):\n        return 1\n"
    assert _ids(bad, "t.py", ["WPS610"]) == ["WPS610"]
    assert _ids(good_sync, "t.py", ["WPS610"]) == []
    assert _ids(good_async, "t.py", ["WPS610"]) == []


def test_wps000_never_fires():
    assert _ids("print(1)\nx = 1\n", "t.py", ["WPS000"]) == []
