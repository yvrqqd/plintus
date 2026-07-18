"""Quote-style utilities that preserve string values when rewriting."""

from __future__ import annotations

import re

from plintus.rules.cbp_helpers import is_log_method_call

_STRING_RE = re.compile(
    r"^(?P<prefix>[rRuUfFbB]*)(?P<quote>'''|\"\"\"|'|\")(?P<body>.*)(?P=quote)$",
    re.DOTALL,
)


def parse_string_literal(text: str) -> tuple[str, str, str] | None:
    """Return (prefix, quote, body) or None if not a simple string literal node."""
    m = _STRING_RE.match(text)
    if not m:
        return None
    return m.group("prefix"), m.group("quote"), m.group("body")


def quote_style(quote: str) -> str:
    if quote in ("'", "'''"):
        return "single"
    return "double"


def desired_quote_char(style: str, *, triple: bool) -> str:
    if style == "single":
        return "'''" if triple else "'"
    return '"""' if triple else '"'


def can_safely_requote(body: str, new_quote: str) -> bool:
    """True if rewriting with new_quote does not require changing escapes in body.

    For triple quotes, also rejects bodies that *end* with the new quote's
    character: ``''' + body + '''`` would form 4+ consecutive same quotes
    (``body'''`` + closing ``'''``) and parse as an unterminated string.
    """
    if new_quote in ("'", "'''"):
        if new_quote == "'":
            return "'" not in body or _all_quotes_escaped(body, "'")
        # triple single
        if "'''" in body:
            return False
        return not body.endswith("'")
    if new_quote == '"':
        return '"' not in body or _all_quotes_escaped(body, '"')
    # triple double
    if '"""' in body:
        return False
    return not body.endswith('"')


def _all_quotes_escaped(body: str, q: str) -> bool:
    i = 0
    while i < len(body):
        if body[i] == "\\":
            i += 2
            continue
        if body.startswith(q, i):
            return False
        i += 1
    return True


def is_fstring(prefix: str) -> bool:
    return "f" in prefix.lower()


def can_switch_quotes(text: str, style: str) -> bool:
    """True if the literal already matches ``style`` or can be rewritten without escape changes."""
    parsed = parse_string_literal(text)
    if parsed is None:
        return False
    prefix, quote, body = parsed
    if quote_style(quote) == style:
        return True
    triple = len(quote) == 3
    new_q = desired_quote_char(style, triple=triple)
    return can_safely_requote(body, new_q)


def requote(text: str, style: str) -> tuple[str, bool] | None:
    """Return (new_text, safe) or None if not applicable / already correct / unsafe.

    f-strings are rewritten only when the body needs no escape changes, but the
    resulting fix is marked ``safe=False``: nested same-quote expressions are
    a syntax error on Python < 3.12 (PEP 701), so a linter targeting >=3.10
    should not auto-apply such fixes without an explicit ``--unsafe`` opt-in.
    """
    parsed = parse_string_literal(text)
    if parsed is None:
        return None
    prefix, quote, body = parsed
    if quote_style(quote) == style:
        return None
    triple = len(quote) == 3
    new_q = desired_quote_char(style, triple=triple)
    if not can_safely_requote(body, new_q):
        return None
    safe = not is_fstring(prefix)
    return f"{prefix}{new_q}{body}{new_q}", safe


def is_message_context(call_name: str | None, message_calls: list[str], is_raise: bool) -> bool:
    if is_raise:
        return True
    if call_name is None:
        return False
    names = set(message_calls)
    if call_name in names:
        return True
    # Allow matching the final attribute: web.json_response → json_response
    short = call_name.rsplit(".", 1)[-1]
    if short in names:
        return True
    # LOG.warning / logger.info / … — same receivers as L001/L004
    return is_log_method_call(call_name, message_calls)
