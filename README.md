# plintus

Fast, extensible Python linter for **complex context-dependent rules**.

Complements [Ruff](https://docs.astral.sh/ruff/): use Ruff for standard checks,
`plintus` for project policies that need CST context (quote roles, call
patterns, decorator requirements, argument order, …).

## Install (dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install maturin pytest
maturin develop --release
plintus check .
```

## Example rule surface

```python
from plintus.api import Rule, RuleContext, Fix, Severity

class DictQuotes(Rule):
    id = "Q001"
    message = "Use single quotes for dict string literals"
    severity = Severity.WARNING
    targets = ("string",)

    def check(self, ctx: RuleContext) -> None:
        for node in ctx.nodes:
            if not ctx.in_dict_string(node):
                continue
            text = node.text()
            # Use the safe-requote helper so escapes and f-strings are handled.
            from plintus.rules.string_utils import requote
            result = requote(text, "single")
            if result is None:
                continue
            new_text, _safe = result
            ctx.report(node, fix=Fix.replace(node, new_text))
```

See [examples/local_rules.py](examples/local_rules.py) for a complete,
wired-up custom rule (including `register()` and pyproject wiring).

## Documentation

- [Architecture](docs/architecture.md)
- [CLI reference](docs/cli.md)
- [Configuration reference](docs/configuration.md)
- [Plugin authoring guide](docs/plugin-authoring.md)
- [Rules catalog](docs/rules-catalog.md)
- [Using with Ruff](docs/with-ruff.md)
