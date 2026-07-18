# Using with Ruff

`plintus` is designed to **complement** Ruff, not replace it.

| Concern | Tool |
|---------|------|
| pyflakes, isort, pyupgrade, pycodestyle, bugbear, print (T20), … | **Ruff** |
| Contextual quotes (Q001/Q002), banned APIs, decorator contracts, arg order, CBP, **WPS** | **plintus** |

## Suggested CI

```bash
ruff check .
ruff format --check .
plintus check .
```

## Suggested pyproject

Builtin rules default to `select = ["ALL"]` with `ignore = []` (all
registered rules, including WPS). Prefer Ruff `T20` over `L002` when both
tools run. WPS421 still flags `print`/`eval`/`exec` — ignore one side if noisy:

```toml
[tool.ruff]
line-length = 120

[tool.ruff.lint]
ignore = ["Q000"]  # contextual quotes owned by plintus Q001/Q002

[tool.plintus]
select = ["ALL"]
ignore = ["L002"]  # Ruff T20 owns print; WPS enabled by default
dict-quotes = "single"
message-quotes = "double"
banned-calls = ["eval", "exec"]
message-calls = ["print", "logging.info", "logging.warning", "logging.error", "logging.debug", "logging.critical", "json_response", "web.json_response"]
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

Family prefixes (`"L"`, `"CFG"`, `"WPS"`, `"WPS2"`, …) work in `select` /
`ignore`. See [rules-catalog.md](rules-catalog.md).
