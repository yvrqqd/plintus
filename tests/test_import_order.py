"""Tests for I001 import section order."""

from __future__ import annotations

from plintus.config import Config, load_config
from plintus.engine import apply_diagnostics_fixes, lint_source, load_rules


def _cfg(**kwargs) -> Config:
    base = Config(cache=False, workers=1)
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def _lint(src: str, **cfg_kw):
    cfg = _cfg(select=["I001"], **cfg_kw)
    return lint_source("t.py", src, load_rules(cfg), cfg), cfg


def test_i001_flags_disordered_sections():
    src = """\
import requests
import os
import cbp_logging
import app.pkg
"""
    diags, _ = _lint(src)
    assert len(diags) == 1
    assert diags[0].rule_id == "I001"
    assert diags[0].severity.value == "warning"
    assert diags[0].fix is not None
    assert diags[0].fix.safety == "safe"


def test_i001_fix_four_sections_idempotent():
    src = """\
import requests
import os
from pathlib import Path
from cbp_something.mod import some_func
import cbp_logging
from app.pkg2 import b
import app.pkg1
"""
    expected = """\
import os
from pathlib import Path

import requests

import cbp_logging
from cbp_something.mod import some_func

import app.pkg1
from app.pkg2 import b
"""
    cfg = _cfg(select=["I001"])
    rules = load_rules(cfg)
    diags = lint_source("t.py", src, rules, cfg)
    assert diags and diags[0].fix is not None
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected

    diags2 = lint_source("t.py", new_src, rules, cfg)
    new2, rem2 = apply_diagnostics_fixes(new_src, diags2, unsafe=False)
    assert diags2 == []
    assert new2 == new_src
    assert rem2 == []


def test_i001_relative_is_first_party():
    src = """\
from .local import x
import os
"""
    expected = """\
import os

from .local import x
"""
    diags, cfg = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_cbp_section_between_third_and_first():
    src = """\
import app.core
import cbp_utils
import httpx
"""
    expected = """\
import httpx

import cbp_utils

import app.core
"""
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_preserves_future_and_docstring():
    src = '''\
"""Module doc."""
from __future__ import annotations
import app.x
import os
'''
    expected = '''\
"""Module doc."""
from __future__ import annotations
import os

import app.x
'''
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_nested_imports_untouched():
    src = """\
import os

def f():
    import json
    return json
"""
    diags, _ = _lint(src)
    assert diags == []


def test_i001_clean_when_already_ordered():
    src = """\
import os
from pathlib import Path

import requests

import cbp_logging

import app.pkg
"""
    diags, _ = _lint(src)
    assert diags == []


def test_i001_import_before_from_within_section():
    src = """\
from os import path
import sys
"""
    expected = """\
import sys
from os import path
"""
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_known_first_party_config():
    # Without known_first_party, mylib/corp would sort as third-party (with
    # requests). With classification working they form the first-party section
    # after third-party and cbp_*.
    src = """\
import mylib
import requests
import corp.util
import cbp_logging
import os
"""
    expected = """\
import os

import requests

import cbp_logging

import corp.util
import mylib
"""
    diags, _ = _lint(src, known_first_party=["mylib", "corp"])
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected
    # Broken classification (all non-stdlib/cbp as third-party) would yield:
    #   os / corp+mylib+requests / cbp  — assert first-party is last section.
    assert "import cbp_logging\n\nimport corp.util\nimport mylib" in new_src
    assert new_src.index("import requests") < new_src.index("import cbp_logging")
    assert new_src.index("import cbp_logging") < new_src.index("import mylib")


def test_i001_cbp_prefix_config():
    src = """\
import app.x
import dsys_foo
import requests
"""
    expected = """\
import requests

import dsys_foo

import app.x
"""
    diags, _ = _lint(src, cbp_import_prefix="dsys_")
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_blank_line_before_following_code():
    src = "import os\ndef f():\n    pass\n"
    expected = "import os\n\ndef f():\n    pass\n"
    diags, _ = _lint(src)
    assert diags
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_preserves_existing_blank_before_code():
    src = "import sys\nimport os\n\ndef f():\n    pass\n"
    expected = "import os\nimport sys\n\ndef f():\n    pass\n"
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_config_loads_i001_keys(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """\
[tool.plintus]
known-first-party = ["app", "tests"]
cbp-import-prefix = "cbp_"
""",
        encoding="utf-8",
    )
    cfg = load_config(config_path=pyproject)
    assert cfg.known_first_party == ["app", "tests"]
    assert cfg.cbp_import_prefix == "cbp_"
    ctx = cfg.to_rule_context()
    assert ctx.known_first_party == ["app", "tests"]
    assert ctx.cbp_import_prefix == "cbp_"
