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
| `--unsafe` | Also apply fixes marked `safety="unsafe"` (use with `--fix`). |
| `--diff` | Print a unified diff of fixes instead of writing them. Does not modify files. |
| `--select IDS` | Comma-separated rule ids to enable (overrides `[tool.plintus] select`). |
| `--ignore IDS` | Comma-separated rule ids to ignore. |
| `--output-format {text,json}` | Output style. Default `text`. JSON is a list of diagnostic dicts (see `Diagnostic.to_dict`). |
| `--no-cache` | Disable the content-addressed cache for this run. |
| `--workers N` | `0` = auto (default), `1` = disable multiprocessing, `N` = pool size. Negative values are rejected. |
| `--config PATH` | Path to a `pyproject.toml` with a `[tool.plintus]` section. Defaults to walking up from cwd. |

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | No error-severity diagnostics (warnings/info/hint do not fail the run). |
| `1`  | At least one diagnostic with `severity = "error"` was reported. |
| `2`  | Invalid arguments (argparse error). |

> **Note:** Only `error`-severity diagnostics fail the process. `Q001`/`Q002`/`ORD001` are warnings; `BAN001`/`DEC001` are errors. Use `--select`/`--ignore` or the `ignore` config key to control which rules run.

### Examples

```bash
# Lint the current directory
plintus check .

# Lint and apply safe fixes
plintus check src/ --fix

# Preview fixes without writing
plintus check src/ --diff

# JSON output for CI integration
plintus check src/ --output-format json --no-cache

# Run only Q001 and Q002
plintus check src/ --select Q001,Q002
```

## `python -m plintus`

Equivalent to the `plintus` console script. Running with no subcommand
prints help and exits `0`.
