# plintus

Extensible Python linter for **complex context-dependent rules**.

Complements [Ruff](https://docs.astral.sh/ruff/) for standard checks; use `plintus`
for project policies that need CST context. Includes a clean-room **WPS** pack —
see [docs/rules-catalog.md](docs/rules-catalog.md).

## Install (as a dependency)

You do not need to clone this repo. Add it as a uv source:

```toml
# pyproject.toml
[project]
dependencies = ["plintus"]

[tool.uv.sources]
plintus = { git = "https://github.com/yvrqqd/plintus.git" }
```

```bash
uv sync
```

Requires a Rust toolchain (the package builds via maturin).

## Documentation

- [Development](docs/development.md)
- [Architecture](docs/architecture.md)
- [CLI reference](docs/cli.md)
- [Configuration reference](docs/configuration.md)
- [Plugin authoring guide](docs/plugin-authoring.md)
- [Rules catalog](docs/rules-catalog.md)
- [Using with Ruff](docs/with-ruff.md)
