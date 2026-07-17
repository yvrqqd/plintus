# Configuration reference

`plintus` reads configuration from the `[tool.plintus]` section of a
`pyproject.toml` discovered by walking up from the current directory (or from
the directory of an explicit `--config` file). Keys accept both `kebab-case`
and `snake_case` forms.

## Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `select` | `list[str]` | `["Q001", "Q002", "ORD001", "BAN001", "DEC001"]` | Rule ids to enable. `"ALL"` enables every loaded rule. Empty `select` enables all (subject to `ignore`). |
| `ignore` | `list[str]` | `[]` | Rule ids to skip (takes precedence over `select`). |
| `workers` | `int` | `0` | `0` = auto (pool size = `min(32, cpu_count)` above the file-count threshold), `1` = disable multiprocessing, `N` = explicit pool size. Negative values are rejected. |
| `worker-threshold` | `int` | `32` | Minimum file count before workers are spawned. Below this, lint runs inline. |
| `cache` | `bool` | `true` | Enable the content-addressed cache. |
| `cache-dir` | `str` | `".plintus_cache"` | Directory for cache files. |
| `dict-quotes` | `"single" \| "double"` | `"single"` | Quote style for strings inside dict literals (Q001). |
| `message-quotes` | `"single" \| "double"` | `"double"` | Quote style for message strings (Q002). |
| `message-calls` | `list[str]` | see below | Call names whose string arguments are treated as messages. |
| `banned-calls` | `list[str]` | `["eval", "exec"]` | Call names forbidden by BAN001. |
| `require-decorators` | `dict[str, list[str]]` | `{}` | Function name → list of required decorator names (DEC001). |
| `call-arg-order` | `dict[str, list[str]]` | `{}` | Call name → required keyword argument order (ORD001). |
| `local-rules` | `list[str]` | `[]` | Paths to Python files defining custom rules. Relative paths resolve against the pyproject directory. |

### Default `message-calls`

```toml
message-calls = [
  "print",
  "logging.info",
  "logging.warning",
  "logging.error",
  "logging.debug",
  "logging.critical",
  "json_response",
  "web.json_response",
]
```

The final segment is also matched as a short name: `web.json_response` matches a
call to `json_response` regardless of the receiver (see
[plugin-authoring.md](plugin-authoring.md) for matching semantics).

## Validation

`Config.__post_init__` validates at construction:

- `dict-quotes` and `message-quotes` must be `"single"` or `"double"`.
- `workers` must be `>= 0`.
- `worker-threshold` must be `>= 1`.

Invalid values raise `ValueError` (so a bad `pyproject.toml` fails loudly
rather than silently misbehaving).

## Cache key composition

The cache key is `SHA-256(source || config_fingerprint || rules_hash || core_api_version)`.

- `config_fingerprint` is the JSON of all `Config` fields except private ones
  (e.g. `_base_dir`), so the cache key is stable regardless of where the
  pyproject lives.
- `rules_hash` includes each rule's id, `api_version`, **and a hash of the
  rule's `check` method source** — so changing rule logic without bumping
  `api_version` correctly invalidates the cache.

## Example

```toml
[tool.plintus]
select = ["Q001", "Q002", "BAN001", "DEC001"]
workers = 0
cache = true
dict-quotes = "single"
message-quotes = "double"
message-calls = ["print", "logging.info", "logging.warning", "logging.error", "json_response"]
banned-calls = ["eval", "exec"]
require-decorators = { handle_event = ["login_required"] }
call-arg-order = { "client.request" = ["method", "url", "timeout"] }
local-rules = ["rules/custom.py"]
```

## Worker limitations

Multiprocessing workers can only reconstruct **builtin** rules (via
`plintus.rules.register`). When `local-rules` or entry-point plugins are
active, `plintus` automatically falls back to single-process lint and
prints a warning to stderr — this prevents silent diagnostic loss. (See
[architecture.md](architecture.md) for the rationale.)
