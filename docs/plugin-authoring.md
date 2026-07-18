# Plugin authoring guide

`plintus` rules are plain Python classes subclassing
[`plintus.api.Rule`](../src/plintus/api.py). Rules run once per file
with a `RuleContext` that exposes the normalized CST and the rule config.

## A minimal rule

```python
from plintus.api import Rule, RuleContext, Severity

class NoTodoComments(Rule):
    id = "X001"
    message = "TODO comments are not allowed"
    severity = Severity.HINT
    targets = ("comment",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            if "TODO" in node.text().upper():
                ctx.report(node, "Remove TODO or track it in an issue tracker")
```

## Registering rules

A rule file is loaded by either:

1. **`local-rules`** in `pyproject.toml` — a list of file paths (relative to
   the pyproject directory):

   ```toml
   [tool.plintus]
   local-rules = ["rules/custom.py"]
   select = ["X001"]
   ```

   The file may define a top-level `register()` returning a list of `Rule`
   instances, or any `Rule` subclasses (auto-instantiated).

2. **Entry points** (for distributable plugins) — add to your plugin's
   `pyproject.toml`:

   ```toml
   [project.entry-points."plintus.plugins"]
   myplugin = "myplugin.plintus_rules:register"
   ```

   The entry point must be a callable returning a `list[Rule]` or a single
   `Rule`. Built-in rules are **always** loaded; plugin rules are merged on
   top, with builtins winning on id collisions.

## `Rule` attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique rule id (required). |
| `message` | `str` | Default message used when `ctx.report` omits one. |
| `severity` | `Severity` | `ERROR`, `WARNING`, `INFO`, or `HINT`. |
| `targets` | `Sequence[str]` | CST node kinds to select via `doc.select`. Empty means the whole tree (`doc.select_all()`), so rules can scan every node without listing kinds. |
| `api_version` | `str` | Must match `plintus.API_VERSION` (`"1"`); mismatched rules raise `PluginError` at load time. |

## `RuleContext` API

| Member | Description |
|--------|-------------|
| `ctx.nodes` | The selected `Node` list (per `targets`). |
| `ctx.document` | The `Document` (CST). |
| `ctx.config` | A typed `RuleContextConfig` with `.get(key, default)` / `ctx.config["key"]` access. Core fields: `message_calls`, `dict_quotes`, `message_quotes`, `banned_calls`, `require_decorators`, `call_arg_order`. WPS thresholds also included (e.g. `min_name_length`, `max_name_length`, `nested_classes_whitelist`, `max_returns`, `max_local_variables`, `max_arguments`, `max_cognitive_score`, `max_imports`, … — see `RuleContextConfig` / `Config` in `config.py`). |
| `ctx.path` / `ctx.source` | File path and source text. |
| `ctx.report(node, message=None, *, fix=None, severity=None)` | Emit a `Diagnostic`. |
| `ctx.ancestors(node)` / `ctx.parent(node)` / `ctx.children(node)` | CST navigation. |
| `ctx.has_ancestor_kind(node, kinds)` | True if any ancestor matches one of `kinds`. |
| `ctx.in_dict_string(node)` / `ctx.dict_pair_role(node)` | `"key"` / `"value"` / `None` for strings in dict pairs. |
| `ctx.is_dict_key(node)` / `ctx.is_dict_value(node)` | Convenience over `dict_pair_role`. |
| `ctx.is_subscript_index_string(node)` | True for `obj['key']` / slice-bound string indexes (not `obj[foo("k")]`). |
| `ctx.enclosing_call_name(node)` | Dotted name of the nearest enclosing `call`, or `None`. |
| `ctx.is_raise_message(node)` | True if the string is under a `raise_statement`. |

## Public helpers

`plintus.resolve_call_name(document, call_node) -> str | None` — resolve
the dotted name of a `call` node (`foo()`, `a.b.c()`, parenthesized receivers
best-effort). Use this instead of the private `_call_name`.

## Fixes

```python
from plintus.api import Fix

fix = Fix.replace(node, new_text, safety="safe")  # or "unsafe"
ctx.report(node, "...", fix=fix)
```

`safety` is validated to be exactly `"safe"` or `"unsafe"` — typos raise
`ValueError` at construction. Unsafe fixes are only applied when the user
passes `--unsafe` to `plintus check --fix`.

Fixes use **UTF-8 byte offsets** (tree-sitter spans). The engine applies
non-overlapping fixes from end to start; overlapping fixes are skipped and
remain in the diagnostic list.

## Message-context matching (`is_message_context`)

A string is treated as a "message" (Q002) when:

- it is under a `raise_statement`, **or**
- its enclosing call name is in `message_calls`, matched either exactly
  (`logging.info`) or by final segment (`web.json_response` matches a
  configured `json_response`), **or**
- it is a log method on a known logger receiver (`LOG.warning`,
  `logger.info`, `logging.error`, …) — same recognition as L001/L004,

**and** the string is not inside a dict literal or a subscript index.
Dict keys/values (including logging `extra={...}` slots) and field access
like `obj['key']` stay under Q001 / `dict_quotes` (default single quotes).

## Example

See [examples/local_rules.py](../examples/local_rules.py) and
[examples/sample_violations.py](../examples/sample_violations.py) for a
runnable demo.
