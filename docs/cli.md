# CLI reference

```
plintus [--version] <command> [options]
```

## `plintus check`

Lint files or directories.

```
plintus check [PATHS...] [options]
```

### Positional arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATHS`  | `.`     | Files or directories to lint. Directories are walked recursively with `.gitignore` support; `.py` and `.pyi` files are included. |

### Options

| Flag | Description |
|------|-------------|
| `--fix` | Apply safe fixes in place (rewrites files). |
| `--unsafe` | Also apply fixes marked `safety="unsafe"`. Requires `--fix` or `--diff` (exit `2` otherwise). |
| `--diff` | Print a unified diff of fixes instead of writing them. Does not modify files. |
| `--select IDS` | Comma-separated rule ids or family prefixes to enable (overrides `[tool.plintus] select`). Prefixes like `L`, `WPS`, `S3G` match that family (remainder must be all digits). |
| `--ignore IDS` | Comma-separated rule ids or family prefixes to ignore. |
| `--output-format {text,json}` | Output style. Default `text`. JSON is a list of diagnostic dicts (see `Diagnostic.to_dict`), including an `applied` bool when `--fix`/`--diff` ran. Text mode hides diagnostics whose fixes were applied. |
| `--no-cache` | Disable the content-addressed cache for this run. |
| `--workers N` | `0` = auto (default), `1` = disable multiprocessing, `N` = pool size. Negative values are rejected. |
| `--config PATH` | Path to a `pyproject.toml` with a `[tool.plintus]` section. Defaults to walking up from cwd. |

Path skipping uses the config-only `exclude` key (list of path prefixes relative to cwd, e.g. `"tests/fixtures"`). There is no `--exclude` CLI flag.

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | No error-severity diagnostics (warnings/info/hint do not fail the run). |
| `1`  | At least one diagnostic with `severity = "error"` was reported. |
| `2`  | Invalid arguments (argparse error). |

> **Note:** Only `error`-severity diagnostics fail the process. Built-in
> severities: `Q001` / `Q002` / `I001` / `ORD001` / `CLS002` are **warnings**; MVP policy rules
> (`BAN001`, `DEC001`) plus CBP and WPS rules are **errors** unless you change
> severity in a plugin. Warnings, info, and hints do not fail the run. Use
> `--select`/`--ignore` or the `ignore` config key to control which rules run.

### Examples

```bash
# Lint the current directory
plintus check .

# Lint and apply safe fixes
plintus check src/ --fix

# Preview fixes without writing
plintus check src/ --diff

# Safe + unsafe fixes (requires --fix or --diff)
plintus check src/ --fix --unsafe

# JSON output for CI integration (includes applied: true/false after --fix)
plintus check src/ --fix --output-format json --no-cache

# Run only Q001 and Q002
plintus check src/ --select Q001,Q002
```

## `python -m plintus`

Equivalent to the `plintus` console script. Running with no subcommand
prints help and exits `0`.
