from __future__ import annotations

import pytest

from plintus.rules.string_utils import parse_string_literal, requote


def test_requote_roundtrip_preserves_body():
    samples = ['"abc"', "'abc'", '""', "''", 'r"path"', "u'x'"]
    for text in samples:
        parsed = parse_string_literal(text)
        assert parsed is not None
        prefix, quote, body = parsed
        target = "double" if quote in ("'", "'''") else "single"
        result = requote(text, target)
        if result is None:
            continue
        new_text, safe = result
        assert safe
        again = parse_string_literal(new_text)
        assert again is not None
        assert again[0] == prefix
        assert again[2] == body


def test_requote_triple_body_ends_with_quote_char():
    # body `it'` ends with `'` → switching to triple-single would form `'''it''''`
    # (4 trailing single quotes) → SyntaxError. Must return None.
    assert requote('"""it\'"""', "single") is None
    # body `it"` ends with `"` → switching to triple-double would form `"""it""""`
    # (4 trailing double quotes) → SyntaxError. Must return None.
    text = "'''" + 'it"' + "'''"
    assert requote(text, "double") is None


@pytest.mark.parametrize(
    "text,style",
    [
        ('"abc"', "single"),
        ("'abc'", "double"),
        ('"""triple"""', "single"),
        ("'''triple'''", "double"),
        ('"""it\'"""', "single"),  # body ends with ' → triple-single unsafe
        ("'''it\"'''", "double"),  # body ends with " → triple-double unsafe
        ('"plain"', "single"),
        ("'he said \"hi\"'", "double"),
        ('r"raw"', "single"),
        ("u'unicode'", "double"),
        ('""', "single"),
        ("''", "double"),
        ('"ends with \\""', "single"),
        ("'no quotes here'", "double"),
        ('"""multi\nline"""', "single"),
        ("'''has \\' escape'''", "double"),
    ],
)
def test_requote_result_compiles(text, style):
    """Every non-None requote result must be a syntactically valid string literal."""
    result = requote(text, style)
    if result is None:
        return
    new_text, _safe = result
    compile(new_text, "<requote>", "eval")
