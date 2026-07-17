# Using with Ruff

`plintus` is designed to **complement** Ruff, not replace it.

| Concern | Tool |
|---------|------|
| pyflakes, isort, pyupgrade, pycodestyle, bugbear, … | **Ruff** |
| Project-specific CST policies (quote roles, banned APIs, decorator contracts, arg order) | **plintus** |

## Suggested CI

```bash
ruff check .
ruff format --check .
plintus check .
```

## Suggested pyproject

```toml
[tool.ruff]
line-length = 100

[tool.plintus]
select = ["Q001", "Q002", "BAN001"]
dict-quotes = "single"
message-quotes = "double"
banned-calls = ["eval", "exec"]
message-calls = ["print", "logging.info", "logging.warning", "logging.error", "logging.debug", "logging.critical", "json_response", "web.json_response"]
```
