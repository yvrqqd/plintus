"""Tests for CBP rules and prefix select/ignore."""

from __future__ import annotations

import pytest

from plintus.config import Config, _matches_rule_id
from plintus.engine import lint_source, load_rules


def _cfg(**kwargs) -> Config:
    base = Config(cache=False, workers=1)
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def _ids(src: str, path: str, select: list[str], *, ignore: list[str] | None = None) -> list[str]:
    cfg = _cfg(select=select, ignore=ignore or [])
    diags = lint_source(path, src, load_rules(cfg), cfg)
    return [d.rule_id for d in diags]


# --- prefix select ---


@pytest.mark.parametrize(
    "rule_id,entry,want",
    [
        ("L001", "L001", True),
        ("L001", "L", True),
        ("L001", "L0", True),
        ("SQL001", "SQL", True),
        ("S3G001", "S3G", True),
        ("S3G001", "S", False),  # digit after S is not enough; remainder must be all digits
        ("E001", "E", True),
        ("ERR", "E", False),
        ("L001", "A", False),
        ("Q001", "Q", True),
        ("BAN001", "BAN", True),
    ],
)
def test_matches_rule_id(rule_id: str, entry: str, want: bool):
    assert _matches_rule_id(rule_id, entry) is want


def test_prefix_select_and_ignore():
    src = 'print(1)\nLOG.info("hi")\n'
    cfg = _cfg(select=["L"], ignore=["L002"])
    rules = load_rules(cfg)
    assert any(r.id == "L001" for r in rules)
    assert all(r.id != "L002" for r in rules)
    diags = lint_source("t.py", src, rules, cfg)
    ids = {d.rule_id for d in diags}
    assert "L001" in ids
    assert "L002" not in ids


def test_default_select_includes_all():
    cfg = _cfg()  # default select = ["ALL"], ignore = []
    rules = load_rules(cfg)
    ids = {r.id for r in rules}
    assert "Q001" in ids
    assert "L001" in ids
    assert "CFG001" in ids
    assert "SQL001" in ids
    assert "S3G001" in ids
    # WPS is enabled by default (ignore = [])
    assert "WPS421" in ids
    assert cfg.enabled("WPS421")


def test_wps_can_be_ignored():
    cfg = _cfg(ignore=["WPS"])
    assert not cfg.enabled("WPS421")
    assert "WPS421" not in {r.id for r in load_rules(cfg)}


# --- L* ---


def test_l001_positional_vs_msg():
    bad = 'LOG.info("hi")\n'
    good = 'LOG.info(msg="hi")\n'
    assert _ids(bad, "t.py", ["L001"]) == ["L001"]
    assert _ids(good, "t.py", ["L001"]) == []
    # Non-logger `.info` must not trigger L001
    assert _ids('response.info("hi")\n', "t.py", ["L001"]) == []


def test_l002_print():
    assert _ids("print(1)\n", "t.py", ["L002"]) == ["L002"]


def test_l003_basic_config():
    src = "import logging\nlogging.basicConfig()\nlogging.config.dictConfig({})\n"
    ids = _ids(src, "t.py", ["L003"])
    assert ids.count("L003") == 2


def test_l004_nested_tags():
    bad = 'LOG.info(msg="x", extra={"tags": {"a": 1}})\n'
    good = 'LOG.info(msg="x", extra={"a": 1})\n'
    assert _ids(bad, "t.py", ["L004"]) == ["L004"]
    assert _ids(good, "t.py", ["L004"]) == []
    assert _ids('response.info(msg="x", extra={"tags": 1})\n', "t.py", ["L004"]) == []


def test_l005_get_logger():
    bad = 'import logging\nlogging.getLogger("app")\n'
    good = "import logging\nlogging.getLogger(__name__)\n"
    good_kw = "import logging\nlogging.getLogger(name=__name__)\n"
    assert _ids(bad, "t.py", ["L005"]) == ["L005"]
    assert _ids(good, "t.py", ["L005"]) == []
    assert _ids(good_kw, "t.py", ["L005"]) == []
    bad_kw = 'import logging\nlogging.getLogger(name="app")\n'
    assert _ids(bad_kw, "t.py", ["L005"]) == ["L005"]
    # Arbitrary *.getLogger must not match
    assert _ids('mylib.getLogger("app")\n', "t.py", ["L005"]) == []
    assert _ids('log.getLogger("app")\n', "t.py", ["L005"]) == []
    # Bare getLogger still flagged
    assert _ids('getLogger("app")\n', "t.py", ["L005"]) == ["L005"]


# --- A* ---


def test_a001_a002():
    src = "import asyncio\nasyncio.get_event_loop()\nasyncio.to_thread(len, [])\n"
    ids = set(_ids(src, "t.py", ["A"]))
    assert ids == {"A001", "A002"}
    # Unrelated receivers must not match
    other = "mylib.get_event_loop()\nmylib.to_thread(len, [])\n"
    assert _ids(other, "t.py", ["A001", "A002"]) == []
    # Imported asyncio alias
    aliased = "import asyncio as aio\naio.get_event_loop()\naio.to_thread(len, [])\n"
    assert set(_ids(aliased, "t.py", ["A"])) == {"A001", "A002"}
    # from asyncio import …
    imported = "from asyncio import get_event_loop, to_thread\nget_event_loop()\nto_thread(len, [])\n"
    assert set(_ids(imported, "t.py", ["A"])) == {"A001", "A002"}
    # Bare without asyncio import must not match
    bare = "get_event_loop()\nto_thread(len, [])\n"
    assert _ids(bare, "t.py", ["A001", "A002"]) == []
    # asyncio.ATTR without import still flagged (catalog name)
    noimp = "asyncio.get_event_loop()\nasyncio.to_thread(len, [])\n"
    assert set(_ids(noimp, "t.py", ["A"])) == {"A001", "A002"}


def test_a003_requests_in_async():
    bad = "import requests\nasync def f():\n    return 1\n"
    good = "import requests\ndef f():\n    return 1\n"
    assert _ids(bad, "t.py", ["A003"]) == ["A003"]
    assert _ids(good, "t.py", ["A003"]) == []
    # Prefix lookalikes must not trigger A003
    lookalike = "import requestsutils\nimport requests_oauthlib\nasync def f():\n    return 1\n"
    assert _ids(lookalike, "t.py", ["A003"]) == []
    # Real requests still flagged when imported alongside other modules
    multi = "import sys, requests\nasync def f():\n    return 1\n"
    assert _ids(multi, "t.py", ["A003"]) == ["A003"]


def test_a004_apprunner():
    bad = "from aiohttp import web\nweb.AppRunner(app)\n"
    good = "from aiohttp import web\nweb.AppRunner(app, handle_signals=False)\n"
    assert _ids(bad, "t.py", ["A004"]) == ["A004"]
    assert _ids(good, "t.py", ["A004"]) == []
    # Unrelated AppRunner must not match
    other = "class AppRunner: pass\nAppRunner()\n"
    assert _ids(other, "t.py", ["A004"]) == []
    bare = "AppRunner(app)\n"
    assert _ids(bare, "t.py", ["A004"]) == []
    # from aiohttp.web import AppRunner [as alias]
    imported = "from aiohttp.web import AppRunner\nAppRunner(app)\n"
    assert _ids(imported, "t.py", ["A004"]) == ["A004"]
    imported_ok = "from aiohttp.web import AppRunner\nAppRunner(app, handle_signals=False)\n"
    assert _ids(imported_ok, "t.py", ["A004"]) == []
    aliased = "from aiohttp.web import AppRunner as AR\nAR(app)\n"
    assert _ids(aliased, "t.py", ["A004"]) == ["A004"]


# --- CFG* ---


def test_cfg001_os_environ():
    src = 'import os\nx = os.environ["A"]\n'
    assert _ids(src, "app/service.py", ["CFG001"]) == ["CFG001"]
    assert _ids(src, "tests/unit/test_x.py", ["CFG001"]) == []
    # Case-insensitive test path segment (norm_parts lowercases)
    assert _ids(src, "Tests/unit/test_x.py", ["CFG001"]) == []
    # from os import environ / bare environ[...]
    alt = 'from os import environ\nx = environ["A"]\n'
    ids = _ids(alt, "app/service.py", ["CFG001"])
    assert "CFG001" in ids
    assert len(ids) >= 2  # import + usage
    assert _ids(alt, "tests/unit/test_x.py", ["CFG001"]) == []
    # Param / def name must not be flagged (only the import)
    param = "from os import environ\ndef f(environ):\n    return 1\n"
    assert _ids(param, "app/service.py", ["CFG001"]) == ["CFG001"]
    defn = "from os import environ\ndef environ():\n    return 1\n"
    assert _ids(defn, "app/service.py", ["CFG001"]) == ["CFG001"]


def test_cfg002_field_alias():
    bad = """
from pydantic import Field
from pydantic_settings import BaseSettings
class S(BaseSettings):
    a: str = Field(default='x')
"""
    good = """
from pydantic import Field
from pydantic_settings import BaseSettings
class S(BaseSettings):
    a: str = Field(default='x', alias='A')
"""
    assert _ids(bad, "app/config/service.py", ["CFG002"]) == ["CFG002"]
    assert _ids(good, "app/config/service.py", ["CFG002"]) == []


def test_cfg003_secret_str():
    bad = """
from pydantic import Field
from pydantic_settings import BaseSettings
class S(BaseSettings):
    db_password: str = Field(default='x', alias='DB_PASSWORD')
"""
    good = """
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings
class S(BaseSettings):
    db_password: SecretStr = Field(default='x', alias='DB_PASSWORD')
"""
    assert _ids(bad, "app/config/db.py", ["CFG003"]) == ["CFG003"]
    assert _ids(good, "app/config/db.py", ["CFG003"]) == []


def test_cfg004_one_settings():
    two = """
from pydantic_settings import BaseSettings
class A(BaseSettings):
    x: str = 'a'
class B(BaseSettings):
    y: str = 'b'
A_SETTINGS = A()
"""
    missing = """
from pydantic_settings import BaseSettings
class A(BaseSettings):
    x: str = 'a'
"""
    good = """
from pydantic_settings import BaseSettings
class A(BaseSettings):
    x: str = 'a'
A_SETTINGS = A()
"""
    assert "CFG004" in _ids(two, "app/config/x.py", ["CFG004"])
    assert "CFG004" in _ids(missing, "app/config/x.py", ["CFG004"])
    assert _ids(good, "app/config/x.py", ["CFG004"]) == []
    assert _ids(missing, "app/other.py", ["CFG004"]) == []


# --- E* ---


def test_e001_bare_exception():
    assert _ids('raise Exception("x")\n', "t.py", ["E001"]) == ["E001"]
    assert _ids('raise ValueError("x")\n', "t.py", ["E001"]) == []


def test_e002_dao_connect():
    src = "async def f(client):\n    await client.connect()\n"
    assert _ids(src, "app/dao/redis/x.py", ["E002"]) == ["E002"]
    assert _ids(src, "app/infra/redis.py", ["E002"]) == []
    # Only app/dao — not an arbitrary dao segment
    assert _ids(src, "vendor/dao/x.py", ["E002"]) == []
    assert _ids(src, "tests/dao/x.py", ["E002"]) == []


def test_e003_slots():
    bad = "class Client:\n    def __init__(self):\n        self._x = 1\n"
    good = "class Client:\n    __slots__ = ('_x',)\n    def __init__(self):\n        self._x = 1\n"
    assert _ids(bad, "app/infra/x.py", ["E003"]) == ["E003"]
    assert _ids(good, "app/infra/x.py", ["E003"]) == []
    assert _ids(bad, "app/dao/x.py", ["E003"]) == ["E003"]
    # manager / bare infra — out of scope
    assert _ids(bad, "app/manager/x.py", ["E003"]) == []
    assert _ids(bad, "infra/x.py", ["E003"]) == []
    # empty marker class (no self.*) — skip
    empty = "class Marker:\n    pass\n"
    assert _ids(empty, "app/infra/x.py", ["E003"]) == []
    # Protocol / Mixin / dataclass — skip
    proto = "from typing import Protocol\nclass P(Protocol):\n    def f(self): ...\n"
    assert _ids(proto, "app/infra/x.py", ["E003"]) == []
    mixin = "class FooMixin:\n    def __init__(self):\n        self._x = 1\n"
    assert _ids(mixin, "app/infra/x.py", ["E003"]) == []
    dc = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class D:\n"
        "    def __init__(self):\n"
        "        self._x = 1\n"
    )
    assert _ids(dc, "app/infra/x.py", ["E003"]) == []
    base_model = (
        "class S(BaseSettings):\n"
        "    def __init__(self):\n"
        "        self._x = 1\n"
    )
    assert _ids(base_model, "app/infra/x.py", ["E003"]) == []


def test_e005_no_slotted_dict_access():
    bad = (
        "class Client:\n"
        "    __slots__ = ('_x',)\n"
        "    def __init__(self):\n"
        "        self._x = 1\n"
        "        self.__dict__['z'] = 2\n"
        "        vars(self)\n"
    )
    ids = _ids(bad, "app/infra/x.py", ["E005"])
    assert ids.count("E005") == 2
    # opt-in __dict__ in slots
    ok_dict = (
        "class Client:\n"
        "    __slots__ = ('_x', '__dict__')\n"
        "    def __init__(self):\n"
        "        self._x = 1\n"
        "        self.__dict__['z'] = 2\n"
    )
    assert _ids(ok_dict, "app/infra/x.py", ["E005"]) == []
    # class namespace access is fine
    class_ns = (
        "class Client:\n"
        "    __slots__ = ('_x',)\n"
        "    def meta(self):\n"
        "        return Client.__dict__\n"
    )
    assert _ids(class_ns, "t.py", ["E005"]) == []
    # no slots → E005 does not apply
    no_slots = (
        "class Client:\n"
        "    def __init__(self):\n"
        "        self.__dict__['z'] = 1\n"
    )
    assert _ids(no_slots, "t.py", ["E005"]) == []


def test_e004_copyright_header():
    good2 = "# Copyright (c) 2024 Acme\n# All rights reserved.\n\nx = 1\n"
    good3 = (
        "# Copyright (c) 2024 Acme\n"
        "# SPDX-License-Identifier: MIT\n"
        "# See LICENSE for details.\n"
        "\n"
        "x = 1\n"
    )
    assert _ids(good2, "t.py", ["E004"]) == []
    assert _ids(good3, "t.py", ["E004"]) == []

    no_header = "x = 1\n"
    one_line = "# Copyright only\n\nx = 1\n"
    four_lines = "# a\n# b\n# c\n# d\n\nx = 1\n"
    assert _ids(no_header, "t.py", ["E004"]) == ["E004"]
    assert _ids(one_line, "t.py", ["E004"]) == ["E004"]
    assert _ids(four_lines, "t.py", ["E004"]) == ["E004"]

    no_blank = "# Copyright (c) 2024 Acme\n# All rights reserved.\nx = 1\n"
    two_blanks = "# Copyright (c) 2024 Acme\n# All rights reserved.\n\n\nx = 1\n"
    assert _ids(no_blank, "t.py", ["E004"]) == ["E004"]
    assert _ids(two_blanks, "t.py", ["E004"]) == ["E004"]

    # leading blank / non-# first line
    leading_blank = "\n# a\n# b\n\nx = 1\n"
    assert _ids(leading_blank, "t.py", ["E004"]) == ["E004"]


# --- G* / SQL / S3 ---


def test_g001_ban_graphene():
    assert _ids("import graphene\n", "t.py", ["G001"]) == ["G001"]
    assert _ids("import strawberry\n", "t.py", ["G001"]) == []
    # Prefix lookalikes must not trigger G001
    lookalike = "import graphene_django\nimport ariadne_codegen\n"
    assert _ids(lookalike, "t.py", ["G001"]) == []
    # Multi-import still flags the banned root
    assert _ids("import sys, graphene\n", "t.py", ["G001"]) == ["G001"]


def test_g002_observe_latency():
    bad = "async def resolve_x(info):\n    return 1\n"
    good = (
        "@observe_latency(protocol='gql', name='x', function_type='handler')\n"
        "async def resolve_x(info):\n    return 1\n"
    )
    assert _ids(bad, "app/api/http/graphql/queries.py", ["G002"]) == ["G002"]
    assert _ids(good, "app/api/http/graphql/queries.py", ["G002"]) == []
    assert _ids(bad, "app/api/http/graphql/context.py", ["G002"]) == []
    # Helpers without resolver signature must not fire
    helper = "def format_name(value):\n    return value\n"
    assert _ids(helper, "app/api/http/graphql/queries.py", ["G002"]) == []


def test_g003_no_dao_in_resolvers():
    src = "from app.dao import s3\nasync def resolve_x(info):\n    return 1\n"
    assert "G003" in _ids(src, "app/api/http/graphql/queries.py", ["G003"])
    # Prefix lookalike must not trigger G003
    lookalike = "from app.dao_extra import s3\nasync def resolve_x(info):\n    return 1\n"
    assert _ids(lookalike, "app/api/http/graphql/queries.py", ["G003"]) == []
    # SQL client method on a DAO-like receiver
    sql = "async def resolve_x(info):\n    await cur.execute('SELECT 1')\n"
    assert "G003" in _ids(sql, "app/api/http/graphql/queries.py", ["G003"])
    # Arbitrary `.execute` is not DAO/SQL
    other = "async def resolve_x(info):\n    await workflow.execute('step')\n"
    assert _ids(other, "app/api/http/graphql/queries.py", ["G003"]) == []


def test_sql001():
    bad_f = 'await cur.execute(f"SELECT {x}")\n'
    bad_fmt = 'await cur.execute("SELECT {}".format(x))\n'
    good = 'await cur.execute("SELECT 1")\n'
    assert _ids(bad_f, "t.py", ["SQL001"]) == ["SQL001"]
    assert _ids(bad_fmt, "t.py", ["SQL001"]) == ["SQL001"]
    assert _ids(good, "t.py", ["SQL001"]) == []
    # Keyword SQL arg
    kw = 'await cur.execute(query=f"SELECT {x}")\n'
    assert _ids(kw, "t.py", ["SQL001"]) == ["SQL001"]
    # Non-DB `.execute` with f-string must not trip SQL001
    other = 'await workflow.execute(f"step-{x}")\n'
    assert _ids(other, "t.py", ["SQL001"]) == []


def test_s3g001():
    bad = "import gc\ngc.collect()\n"
    assert set(_ids(bad, "app/dao/s3.py", ["S3G"])) == {"S3G001"}
    # may report import + call = 2 diagnostics same id
    assert len(_ids(bad, "app/dao/s3.py", ["S3G001"])) >= 1
    assert _ids(bad, "app/manager/x.py", ["S3G001"]) == []
    # path with unrelated "s3" segment must not match
    assert _ids(bad, "app/vendor/s3compat/util.py", ["S3G001"]) == []
    # Prefix lookalikes must not trigger S3G001 import check
    lookalike = "import gcc\nimport gctypes\n"
    assert _ids(lookalike, "app/dao/s3.py", ["S3G001"]) == []
    # Multi-import still flags real gc
    assert "S3G001" in _ids("import sys, gc\n", "app/dao/s3.py", ["S3G001"])
    # Substring "gc" in receiver must not false-positive (bagcollector.collect)
    fp = "bagcollector.collect()\n"
    assert _ids(fp, "app/dao/s3.py", ["S3G001"]) == []
    # Attribute chain ending in .gc.collect still flagged
    assert "S3G001" in _ids("mod.gc.collect()\n", "app/dao/s3.py", ["S3G001"])
