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
    assert "WPS328" not in ids  # still planned
    assert "WPS440" not in ids
    assert "WPS527" not in ids
    # Implemented / partial codes stay registered.
    assert "WPS308" in ids
    assert "WPS421" in ids
    assert "WPS428" in ids
    assert "WPS476" in ids
    assert "WPS451" in ids
    assert "WPS511" in ids
    assert "WPS523" in ids
    assert "WPS443" in ids
    assert "WPS481" in ids
    assert "WPS474" in ids


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


def test_wps443_unhashable_in_hash():
    assert "WPS443" in _ids("{[]}\n", "t.py", ["WPS443"])
    assert "WPS443" in _ids("{ {}: 1}\n", "t.py", ["WPS443"])
    assert "WPS443" in _ids("{[]: 1}\n", "t.py", ["WPS443"])
    assert _ids("{(1, 2): 1}\n", "t.py", ["WPS443"]) == []


def test_wps444_false_and_true_or():
    assert "WPS444" in _ids("if False and x:\n    pass\n", "t.py", ["WPS444"])
    assert "WPS444" in _ids("if True or x:\n    pass\n", "t.py", ["WPS444"])
    assert _ids("if x and y:\n    pass\n", "t.py", ["WPS444"]) == []


def test_wps445_bad_starred_keyword():
    assert "WPS445" in _ids('f(**{"not-valid": 1})\n', "t.py", ["WPS445"])
    assert _ids('f(**{"valid": 1})\n', "t.py", ["WPS445"]) == []


def test_wps446_approximate_constants():
    assert "WPS446" in _ids("x = 3.14\n", "t.py", ["WPS446"])
    assert "WPS446" in _ids("x = 2.718\n", "t.py", ["WPS446"])
    assert _ids("x = 3.15\n", "t.py", ["WPS446"]) == []
    assert _ids("x = 3.1\n", "t.py", ["WPS446"]) == []


def test_wps447_alphabet_string():
    assert "WPS447" in _ids('s = "abcdefghijklmnopqrstuvwxyz"\n', "t.py", ["WPS447"])
    assert _ids('s = "abc"\n', "t.py", ["WPS447"]) == []


def test_wps449_float_keys():
    assert "WPS449" in _ids("{1.0: 1}\n", "t.py", ["WPS449"])
    assert "WPS449" in _ids("x[1.0]\n", "t.py", ["WPS449"])
    assert _ids("{1: 1}\n", "t.py", ["WPS449"]) == []


def test_wps455_nontrivial_except():
    bad = "try:\n    pass\nexcept SomeCall():\n    pass\n"
    good = "try:\n    pass\nexcept ValueError:\n    pass\n"
    good_attr = "try:\n    pass\nexcept mod.Err:\n    pass\n"
    assert "WPS455" in _ids(bad, "t.py", ["WPS455"])
    assert _ids(good, "t.py", ["WPS455"]) == []
    assert _ids(good_attr, "t.py", ["WPS455"]) == []


def test_wps460_single_element_destructuring():
    assert "WPS460" in _ids("a, = [1]\n", "t.py", ["WPS460"])
    assert "WPS460" in _ids("(a,) = [1]\n", "t.py", ["WPS460"])
    assert _ids("a, b = [1, 2]\n", "t.py", ["WPS460"]) == []


def test_wps468_enumerate_placeholder():
    bad = "for _, x in enumerate(xs):\n    pass\n"
    good = "for i, x in enumerate(xs):\n    pass\n"
    assert "WPS468" in _ids(bad, "t.py", ["WPS468"])
    assert _ids(good, "t.py", ["WPS468"]) == []


def test_wps469_raise_from_itself():
    assert "WPS469" in _ids("raise e from e\n", "t.py", ["WPS469"])
    assert _ids("raise e from other\n", "t.py", ["WPS469"]) == []


def test_wps470_class_kwargs_unpack():
    assert "WPS470" in _ids("class A(**kwargs):\n    pass\n", "t.py", ["WPS470"])
    assert _ids("class A(Base):\n    pass\n", "t.py", ["WPS470"]) == []


def test_wps471_consecutive_slices():
    assert "WPS471" in _ids("x = y[1:][:2]\n", "t.py", ["WPS471"])
    assert _ids("x = y[1:3]\n", "t.py", ["WPS471"]) == []
    assert _ids("x = y[1][2]\n", "t.py", ["WPS471"]) == []


def test_wps472_first_via_unpacking():
    assert "WPS472" in _ids("first, *_ = items\n", "t.py", ["WPS472"])
    assert "WPS472" in _ids("first, *rest = items\n", "t.py", ["WPS472"])
    assert _ids("a, b = items\n", "t.py", ["WPS472"]) == []
    assert _ids("a, *b, c = items\n", "t.py", ["WPS472"]) == []


def test_wps474_import_alias_collision():
    bad = "from x import a as b\nfrom x import a as c\n"
    same = "from x import a as b\nfrom x import a as b\n"
    mixed = "from module import name, name as alias\n"
    assert "WPS474" in _ids(bad, "t.py", ["WPS474"])
    assert "WPS474" in _ids(mixed, "t.py", ["WPS474"])
    assert _ids(same, "t.py", ["WPS474"]) == []


def test_wps481_leaking_for_loop():
    mod = "for x in y:\n    pass\n"
    cls = "class C:\n    for x in y:\n        pass\n"
    fn = "def f():\n    for x in y:\n        pass\n"
    assert "WPS481" in _ids(mod, "t.py", ["WPS481"])
    assert "WPS481" in _ids(cls, "t.py", ["WPS481"])
    assert _ids(fn, "t.py", ["WPS481"]) == []


def test_wps511_multiple_isinstance_same_var():
    bad = "if isinstance(x, int) or isinstance(x, str):\n    pass\n"
    good = "if isinstance(x, (int, str)):\n    pass\n"
    assert "WPS511" in _ids(bad, "t.py", ["WPS511"])
    assert _ids(good, "t.py", ["WPS511"]) == []


def test_wps512_isinstance_single_item_tuple():
    assert "WPS512" in _ids("isinstance(x, (int,))\n", "t.py", ["WPS512"])
    assert _ids("isinstance(x, int)\n", "t.py", ["WPS512"]) == []
    assert _ids("isinstance(x, (int, str))\n", "t.py", ["WPS512"]) == []
    # Object being a one-tuple must not false-positive.
    assert _ids("isinstance((x,), int)\n", "t.py", ["WPS512"]) == []
    assert _ids("isinstance(foo(bar=(1,)), Baz)\n", "t.py", ["WPS512"]) == []


def test_wps513_implicit_elif():
    bad = "if a:\n    pass\nelse:\n    if b:\n        pass\n"
    good = "if a:\n    pass\nelif b:\n    pass\n"
    assert "WPS513" in _ids(bad, "t.py", ["WPS513"])
    assert _ids(good, "t.py", ["WPS513"]) == []


def test_wps514_multiple_equality_same_var():
    bad = "if x == 1 or x == 2:\n    pass\n"
    good = "if x in {1, 2}:\n    pass\n"
    assert "WPS514" in _ids(bad, "t.py", ["WPS514"])
    assert _ids(good, "t.py", ["WPS514"]) == []


def test_wps517_useless_starred():
    assert "WPS517" in _ids("f(*[a, b])\n", "t.py", ["WPS517"])
    assert "WPS517" in _ids("[*(1, 2)]\n", "t.py", ["WPS517"])
    assert _ids("f(*args)\n", "t.py", ["WPS517"]) == []


def test_wps519_implicit_sum():
    bad = "total = 0\nfor x in xs:\n    total += x\n"
    good = "total = sum(xs)\n"
    assert "WPS519" in _ids(bad, "t.py", ["WPS519"])
    assert _ids(good, "t.py", ["WPS519"]) == []


def test_wps522_implicit_primitive_lambda():
    assert "WPS522" in _ids("f = lambda: []\n", "t.py", ["WPS522"])
    assert "WPS522" in _ids("f = lambda: {}\n", "t.py", ["WPS522"])
    assert "WPS522" in _ids("f = lambda: 0\n", "t.py", ["WPS522"])
    assert _ids("f = lambda: x\n", "t.py", ["WPS522"]) == []


def test_wps524_misrefactored_self_assignment():
    assert "WPS524" in _ids("self.x = self.x\n", "t.py", ["WPS524"])
    assert _ids("self.x = self.y\n", "t.py", ["WPS524"]) == []
    assert _ids("x = x\n", "t.py", ["WPS524"]) == []


def test_wps525_in_single_item_container():
    assert "WPS525" in _ids("x in [1]\n", "t.py", ["WPS525"])
    assert "WPS525" in _ids("x in (1,)\n", "t.py", ["WPS525"])
    assert "WPS525" in _ids("x in {1}\n", "t.py", ["WPS525"])
    assert _ids("x in [1, 2]\n", "t.py", ["WPS525"]) == []


def test_wps526_yield_instead_of_yield_from():
    bad = "def g(y):\n    for x in y:\n        yield x\n"
    good = "def g(y):\n    yield from y\n"
    assert "WPS526" in _ids(bad, "t.py", ["WPS526"])
    assert _ids(good, "t.py", ["WPS526"]) == []


def test_wps528_implicit_items():
    bad = "for k in d:\n    print(d[k])\n"
    good = "for k, v in d.items():\n    print(v)\n"
    assert "WPS528" in _ids(bad, "t.py", ["WPS528"])
    assert _ids(good, "t.py", ["WPS528"]) == []


def test_wps529_implicit_get():
    bad = "v = d[k] if k in d else 0\n"
    good = "v = d.get(k, 0)\n"
    assert "WPS529" in _ids(bad, "t.py", ["WPS529"])
    assert _ids(good, "t.py", ["WPS529"]) == []


def test_wps530_implicit_negative_index():
    assert "WPS530" in _ids("x[len(x) - 1]\n", "t.py", ["WPS530"])
    assert _ids("x[-1]\n", "t.py", ["WPS530"]) == []


def test_wps532_is_with_non_singleton_literal():
    assert "WPS532" in _ids("x is 0\n", "t.py", ["WPS532"])
    assert "WPS532" in _ids("x is []\n", "t.py", ["WPS532"])
    assert _ids("x is None\n", "t.py", ["WPS532"]) == []


def test_wps533_duplicate_if_elif_conditions():
    bad = "if a:\n    pass\nelif a:\n    pass\n"
    good = "if a:\n    pass\nelif b:\n    pass\n"
    assert "WPS533" in _ids(bad, "t.py", ["WPS533"])
    assert _ids(good, "t.py", ["WPS533"]) == []


def test_wps534_useless_ternary():
    assert "WPS534" in _ids("x if True else y\n", "t.py", ["WPS534"])
    assert "WPS534" in _ids("a if cond else a\n", "t.py", ["WPS534"])
    assert _ids("a if cond else b\n", "t.py", ["WPS534"]) == []


def test_wps536_extra_match_subject_syntax():
    bad_list = "match [x]:\n    case _:\n        pass\n"
    bad_set = "match {x}:\n    case _:\n        pass\n"
    good = "match x:\n    case _:\n        pass\n"
    assert "WPS536" in _ids(bad_list, "t.py", ["WPS536"])
    assert "WPS536" in _ids(bad_set, "t.py", ["WPS536"])
    assert _ids(good, "t.py", ["WPS536"]) == []


def test_wps308_compare_two_literals():
    assert "WPS308" in _ids("1 == 2\n", "t.py", ["WPS308"])
    assert _ids("x == 1\n", "t.py", ["WPS308"]) == []


def test_wps309_argument_first():
    # Yoda form is forbidden; argument-first is OK.
    assert "WPS309" in _ids("1 == x\n", "t.py", ["WPS309"])
    assert "WPS309" in _ids("3 < x\n", "t.py", ["WPS309"])
    assert _ids("x == 1\n", "t.py", ["WPS309"]) == []
    assert _ids("x > 3\n", "t.py", ["WPS309"]) == []


def test_wps310_uppercase_number_base():
    assert "WPS310" in _ids("x = 0XFF\n", "t.py", ["WPS310"])
    assert "WPS310" in _ids("x = 1E3\n", "t.py", ["WPS310"])
    assert _ids("x = 0xff\n", "t.py", ["WPS310"]) == []


def test_wps311_multiple_in_checks():
    assert "WPS311" in _ids("a in b in c\n", "t.py", ["WPS311"])
    assert _ids("a in b\n", "t.py", ["WPS311"]) == []
    assert _ids("'in' in x\n", "t.py", ["WPS311"]) == []
    assert _ids('x in "in"\n', "t.py", ["WPS311"]) == []


def test_wps315_extra_object_base():
    assert "WPS315" in _ids("class A(B, object):\n    pass\n", "t.py", ["WPS315"])
    assert _ids("class A(B):\n    pass\n", "t.py", ["WPS315"]) == []


def test_wps316_multi_as_target():
    bad = 'with open("f") as (a, b):\n    pass\n'
    good = 'with open("f") as a:\n    pass\n'
    assert "WPS316" in _ids(bad, "t.py", ["WPS316"])
    assert _ids(good, "t.py", ["WPS316"]) == []


def test_wps327_meaningless_continue():
    assert "WPS327" in _ids("for x in y:\n    continue\n", "t.py", ["WPS327"])
    good = "for x in y:\n    if x:\n        continue\n    print(x)\n"
    assert _ids(good, "t.py", ["WPS327"]) == []


def test_wps339_meaningless_zeros():
    assert "WPS339" in _ids("x = 00\n", "t.py", ["WPS339"])
    assert _ids("x = 0\n", "t.py", ["WPS339"]) == []


def test_wps340_extra_plus_exponent():
    assert "WPS340" in _ids("x = 1e+5\n", "t.py", ["WPS340"])
    assert _ids("x = 1e5\n", "t.py", ["WPS340"]) == []


def test_wps341_letters_as_hex():
    assert "WPS341" in _ids("x = 0xabc\n", "t.py", ["WPS341"])
    assert _ids("x = 0xab1\n", "t.py", ["WPS341"]) == []


def test_wps343_uppercase_complex():
    assert "WPS343" in _ids("x = 1J\n", "t.py", ["WPS343"])
    assert _ids("x = 1j\n", "t.py", ["WPS343"]) == []


def test_wps345_meaningless_math():
    assert "WPS345" in _ids("x = y * 1\n", "t.py", ["WPS345"])
    assert "WPS345" in _ids("x = y + 0\n", "t.py", ["WPS345"])
    assert _ids("x = y * 2\n", "t.py", ["WPS345"]) == []


def test_wps346_double_minus():
    assert "WPS346" in _ids("x = --y\n", "t.py", ["WPS346"])
    assert _ids("x = -y\n", "t.py", ["WPS346"]) == []


def test_wps348_line_starts_with_dot():
    assert "WPS348" in _ids("foo\\\n.bar()\n", "t.py", ["WPS348"])
    assert _ids("foo.bar()\n", "t.py", ["WPS348"]) == []


def test_wps351_unnecessary_literal_condition():
    assert "WPS351" in _ids("if []:\n    pass\n", "t.py", ["WPS351"])
    assert "WPS351" in _ids('if "":\n    pass\n', "t.py", ["WPS351"])
    assert _ids("if x:\n    pass\n", "t.py", ["WPS351"]) == []
