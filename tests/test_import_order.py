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


def test_i001_import_before_from_then_alpha():
    src = """\
from sys import path
import os
from pathlib import Path
import abc
from os import walk
"""
    expected = """\
import abc
import os
from os import walk
from pathlib import Path
from sys import path
"""
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_sorts_imported_names():
    src = """\
from os import walk, path, Path as P
import sys, os
"""
    expected = """\
import os, sys
from os import path, Path as P, walk
"""
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_noqa_same_line_already_ordered():
    src = "import os  # noqa: F401\n\ndef f():\n    pass\n"
    diags, _ = _lint(src)
    assert diags == []


def test_i001_noqa_same_line_multi_import_already_ordered():
    src = "import os  # noqa: F401\nimport sys\n"
    diags, _ = _lint(src)
    assert diags == []


def test_i001_type_ignore_stays_on_same_line_when_sorting_names():
    src = "import sys, os  # type: ignore\n"
    expected = "import os, sys  # type: ignore\n"
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_trailing_comment_stays_on_same_logical_import_when_reordering():
    src = "import requests\nimport sys, os  # type: ignore\n"
    expected = "import os, sys  # type: ignore\n\nimport requests\n"
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_blank_line_after_trailing_comment_before_code():
    src = "import os  # noqa: F401\ndef f():\n    pass\n"
    expected = "import os  # noqa: F401\n\ndef f():\n    pass\n"
    diags, _ = _lint(src)
    assert diags
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_parenthesized_from_flattened_and_sorted():
    src = """\
from os import (
    walk,
    path,
)
"""
    expected = """\
from os import path, walk
"""
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_long_from_import_stays_parenthesized():
    """Autofix must not flatten past line-length (default 88)."""
    src = """\
from app.api.http.graphql.schema.mutation import (
    CreateCompany, UpdateCompany, ArchiveCompany,
    CreateAgent, UpdateAgent, ArchiveAgent, AddAgentTag, RemoveAgentTag,
    CreateTag, UpdateTag, RemoveTag
)
"""
    expected = """\
from app.api.http.graphql.schema.mutation import (
    AddAgentTag,
    ArchiveAgent,
    ArchiveCompany,
    CreateAgent,
    CreateCompany,
    CreateTag,
    RemoveAgentTag,
    RemoveTag,
    UpdateAgent,
    UpdateCompany,
    UpdateTag,
)
"""
    diags, _ = _lint(src)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected
    assert all(len(line) <= 88 for line in new_src.splitlines())

    diags2, _ = _lint(new_src)
    assert diags2 == []


def test_i001_long_from_import_respects_line_length_config():
    src = "from pkg import zebra, alpha, beta\n"
    # Fits on one line at default 88; force wrap with a tight limit.
    expected = """\
from pkg import (
    alpha,
    beta,
    zebra,
)
"""
    diags, _ = _lint(src, line_length=20)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected


def test_i001_long_plain_import_splits_statements():
    src = "import module_with_a_rather_long_name_alpha, module_with_a_rather_long_name_beta\n"
    expected = (
        "import module_with_a_rather_long_name_alpha\n"
        "import module_with_a_rather_long_name_beta\n"
    )
    diags, _ = _lint(src, line_length=40)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected

    diags2, _ = _lint(new_src, line_length=40)
    assert diags2 == []


def test_i001_long_plain_import_split_preserves_trailing_comments():
    src = (
        "import module_with_a_rather_long_name_alpha, "
        "module_with_a_rather_long_name_beta  # noqa: F401\n"
    )
    expected = (
        "import module_with_a_rather_long_name_alpha  # noqa: F401\n"
        "import module_with_a_rather_long_name_beta  # noqa: F401\n"
    )
    diags, _ = _lint(src, line_length=40)
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected
    diags2, _ = _lint(new_src, line_length=40)
    assert diags2 == []

    src_ti = (
        "import module_with_a_rather_long_name_alpha, "
        "module_with_a_rather_long_name_beta  # type: ignore\n"
    )
    expected_ti = (
        "import module_with_a_rather_long_name_alpha  # type: ignore\n"
        "import module_with_a_rather_long_name_beta  # type: ignore\n"
    )
    diags_ti, _ = _lint(src_ti, line_length=40)
    new_ti, _ = apply_diagnostics_fixes(src_ti, diags_ti, unsafe=False)
    assert new_ti == expected_ti
    diags_ti2, _ = _lint(new_ti, line_length=40)
    assert diags_ti2 == []


def test_i001_split_import_reinterleaves_sibling_one_fix():
    """Long multi-import split must re-bucket so mid sorts between ends."""
    # Joined "import alpha_…, zeta_…" exceeds 50; mid belongs alphabetically
    # between the split names — one ``--fix`` must be final.
    src = (
        "import alpha_xxxx_long_name_here, zeta_xxxx_long_name_here\n"
        "import mid_pkg\n"
    )
    expected = (
        "import alpha_xxxx_long_name_here\n"
        "import mid_pkg\n"
        "import zeta_xxxx_long_name_here\n"
    )
    diags, _ = _lint(src, line_length=50)
    assert diags
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected
    diags2, _ = _lint(new_src, line_length=50)
    assert diags2 == []


def test_i001_unsorted_multi_import_join_key_one_fix():
    """Name-sort alone must not leave a second-pass join-key reorder."""
    src = "import zebra, alpha\nimport mid\n"
    expected = "import alpha, zebra\nimport mid\n"
    diags, _ = _lint(src)
    assert diags
    new_src, _ = apply_diagnostics_fixes(src, diags, unsafe=False)
    assert new_src == expected
    diags2, _ = _lint(new_src)
    assert diags2 == []


def test_i001_trailing_comment_forces_wrap_when_over_limit():
    src = "from pkg import alpha, beta  # noqa: F401\n"
    expected = """\
from pkg import (
    alpha,
    beta,
)  # noqa: F401
"""
    # Single line without comment fits; with comment it does not.
    diags, _ = _lint(src, line_length=len("from pkg import alpha, beta") + 1)
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
line-length = 100
""",
        encoding="utf-8",
    )
    cfg = load_config(config_path=pyproject)
    assert cfg.known_first_party == ["app", "tests"]
    assert cfg.cbp_import_prefix == "cbp_"
    assert cfg.line_length == 100
    ctx = cfg.to_rule_context()
    assert ctx.known_first_party == ["app", "tests"]
    assert ctx.cbp_import_prefix == "cbp_"
    assert ctx.line_length == 100
