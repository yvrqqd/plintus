# Using with Ruff

`plintus` aims to be **self-sufficient** for project policy and, over time,
standard lint families. Ruff remains useful for families **not yet ported**
(most pycodestyle / pyflakes codes). See the [planned catalog](rules-catalog.md#planned-pep8--flake8--isort-compatibility).

| Concern | Tool |
|---------|------|
| Contextual quotes (Q001/Q002), import sections (**I001**), banned APIs, decorator contracts, arg order, CBP, **WPS** | **plintus** |
| Unported pyflakes (`F`), pycodestyle (`E`/`W` — note CBP already uses `E001`–`E006`), pyupgrade, bugbear, print (T20), … | **Ruff** (optional) |

## Suggested CI

```bash
# Optional while F/E/W are not fully ported:
ruff check .
ruff format --check .
plintus check .
# Autofix imports (I001) + other safe fixes:
# plintus check --fix .
```

## Suggested pyproject

Builtin rules default to `select = ["ALL"]` with `ignore = []` (all
registered rules, including WPS). Prefer Ruff `T20` over `L002` when both
tools run. WPS421 still flags `print`/`eval`/`exec` — ignore one side if noisy.
**Import order:** use plintus `I001` (CBP four sections). If Ruff `I` is also
enabled, ignore `I` on one side to avoid fighting autofixes.

```toml
[tool.ruff]
line-length = 120

[tool.ruff.lint]
ignore = ["Q000", "I"]  # quotes + import order owned by plintus

[tool.plintus]
select = ["ALL"]
ignore = ["L002"]  # Ruff T20 owns print; WPS enabled by default
dict-quotes = "single"
message-quotes = "double"
banned-calls = ["eval", "exec"]
known-first-party = ["app"]
# cbp-import-prefix = "cbp_"
message-calls = ["print", "logging.info", "logging.warning", "logging.error", "logging.debug", "json_response", "web.json_response"]
# Optional WPS thresholds (wemake defaults apply if omitted):
# max-arguments = 5
# max-cognitive-score = 12
```

### Opt out of WPS

```toml
[tool.plintus]
select = ["ALL"]
ignore = ["WPS", "L002"]  # MVP + CBP only
```

### Dual-codes

| Topic | Prefer in Ruff / CBP | Also in plintus WPS |
|-------|----------------------|---------------------|
| print | T20 / L002 | WPS421 |
| star import | F403 | WPS347 |
| complexity | C901 | WPS2xx |
| eval/exec | bandit / BAN001 | WPS421 |
| import order | — | **I001** (plintus; ignore Ruff `I`) |

Family prefixes (`"L"`, `"CFG"`, `"WPS"`, `"WPS2"`, `"I"`, …) work in `select` /
`ignore`. See [rules-catalog.md](rules-catalog.md).
