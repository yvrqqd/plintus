# Configuration reference

`plintus` reads configuration from the `[tool.plintus]` section of a
`pyproject.toml` discovered by walking up from the current directory (or from
the directory of an explicit `--config` file). Keys accept both `kebab-case`
and `snake_case` forms.

## Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `select` | `list[str]` | `["ALL"]` | Rule ids to enable. Exact ids, family prefixes (`"L"` → `L001`…`L006`, `"SQL"` → `SQL001`, `"S3G"` → `S3G001`; remainder after the prefix must be all digits so `"S"` does not match `S3G001`), or `"ALL"`. Empty `select` also enables all (subject to `ignore`). |
| `ignore` | `list[str]` | `[]` | Rule ids / family prefixes to skip (takes precedence over `select`). Empty by default — all registered rules (including WPS) are enabled. |
| `exclude` | `list[str]` | `[]` | Path prefixes to skip after discovery (matched against the path relative to cwd, e.g. `"tests/fixtures"`). |
| `workers` | `int` | `0` | `0` = auto (pool size = `min(32, cpu_count)` above the file-count threshold), `1` = disable multiprocessing, `N` = explicit pool size. Negative values are rejected. |
| `worker-threshold` | `int` | `32` | Minimum file count before workers are spawned. Below this, lint runs inline. |
| `cache` | `bool` | `true` | Enable the content-addressed cache. |
| `cache-dir` | `str` | `".plintus_cache"` | Directory for cache files. |
| `dict-quotes` | `"single" \| "double"` | `"single"` | Quote style for dict literals and subscript indexes (Q001), e.g. `obj['key']`. |
| `message-quotes` | `"single" \| "double"` | `"double"` | Quote style for message strings (Q002). |
| `message-calls` | `list[str]` | see below | Call names whose string arguments are treated as messages. |
| `banned-calls` | `list[str]` | `["eval", "exec"]` | Call names forbidden by BAN001. |
| `require-decorators` | `dict[str, list[str]]` | `{}` | Function name → list of required decorator names (DEC001). |
| `call-arg-order` | `dict[str, list[str]]` | `{}` | Call name → required keyword argument order (ORD001). |
| `known-first-party` | `list[str]` | `["app"]` | Top-level module names treated as first-party for I001 (plus relative imports). |
| `cbp-import-prefix` | `str` | `"cbp_"` | Top-level names starting with this prefix form the CBP import section (I001). |
| `local-rules` | `list[str]` | `[]` | Paths to Python files defining custom rules. Relative paths resolve against the pyproject directory. |

### WPS thresholds

Defaults match [wemake-python-styleguide](https://wemake-python-styleguide.readthedocs.io/en/latest/pages/usage/configuration.html).
Keys accept kebab-case and snake_case.

| Key | Default | Description |
|-----|---------|-------------|
| `min-name-length` | `2` | Minimum effective name length (WPS111) |
| `max-name-length` | `45` | Maximum name length (WPS118) |
| `nested-classes-whitelist` | `["Meta","Params","Config"]` | Allowed nested class names (WPS431) |
| `max-noqa-comments` | `10` | Max `# noqa` comments (WPS402) |
| `allowed-domain-names` | `[]` | Extra allowed short/domain names |
| `forbidden-domain-names` | `[]` | Extra forbidden variable names |
| `known-enum-bases` | `[]` | Extra enum-like base names (WPS115) |
| `max-returns` | `5` | Max `return` statements (WPS212) |
| `max-local-variables` | `5` | Max locals (WPS210) |
| `max-expressions` | `9` | Max expressions in a function (WPS213) |
| `max-arguments` | `5` | Max params excluding self/cls/mcs (WPS211) |
| `max-module-members` | `7` | Max top-level classes/functions (WPS202) |
| `max-methods` | `7` | Max methods per class (WPS214) |
| `max-line-complexity` | `14` | Max nodes per line (WPS221) |
| `max-jones-score` | `12` | Module Jones score (WPS200) |
| `max-imports` | `12` | Max import statements (WPS201) |
| `max-imported-names` | `50` | Max imported names (WPS203) |
| `max-base-classes` | `3` | Max bases (WPS215) |
| `max-decorators` | `5` | Max decorators (WPS216) |
| `max-string-usages` | `3` | Max repeated string literals (WPS226) |
| `max-awaits` | `5` | Max awaits (WPS217) |
| `max-try-body-length` | `1` | Max statements in try body (WPS229) |
| `max-module-expressions` | `7` | Overused module expressions (WPS204) |
| `max-function-expressions` | `4` | Overused expressions inside a function (WPS204) |
| `max-asserts` | `5` | Max asserts (WPS218) |
| `max-access-level` | `4` | Max attribute chain depth (WPS219) |
| `max-attributes` | `6` | Max public instance attrs (WPS230) |
| `max-raises` | `3` | Max raises (WPS238) |
| `max-except-exceptions` | `3` | Max exceptions in except (WPS239) |
| `max-cognitive-score` | `12` | Cognitive complexity per function (WPS231) |
| `max-cognitive-average` | `8` | Average cognitive complexity (WPS232) |
| `max-call-level` | `3` | Max call chain depth (WPS233) |
| `max-annotation-complexity` | `3` | Nested annotation depth (WPS234) |
| `max-import-from-members` | `8` | Max names in import-from (WPS235) |
| `max-tuple-unpack-length` | `4` | Max unpack targets (WPS236) |
| `max-type-params` | `6` | Max PEP 695 type params (WPS240) |
| `max-match-subjects` | `7` | Max match subjects (WPS241) |
| `max-match-cases` | `7` | Max match cases (WPS242) |
| `max-lines-in-finally` | `2` | Max finally body stmts (WPS243) |
| `max-conditions` | `4` | Max boolean conditions (WPS222) |

Also accepted (lists):

- `allowed-module-metadata` / `forbidden-module-metadata` — WPS410 (defaults
  forbid `copyright` / `license` when `forbidden-module-metadata` is empty).
- `forbidden-inline-ignore` — WPS461 (codes banned in `# noqa: …`; empty = off).

Integer: `exps-for-one-empty-line` (default `2`) — reserved for WPS473
(currently planned; loaded and fingerprinted, not yet checked).

### Default `message-calls`

```toml
message-calls = [
  "print",
  "logging.info",
  "logging.warning",
  "logging.error",
  "logging.debug",
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
select = ["ALL"]
# ignore = ["WPS"]  # optional: drop the WPS family
workers = 0
cache = true
dict-quotes = "single"
message-quotes = "double"
message-calls = ["print", "logging.info", "logging.warning", "logging.error", "logging.debug", "json_response", "web.json_response"]
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
