# plintus rules catalog (final)

Decisions locked in:

- **Quotes:** contextual only — `Q001` / `Q002` (not global flake8-quotes / Ruff `Q000`).
- **flake8/Ruff:** maximum code compatibility (`F`, `E`, `W`, `I`, … same IDs).
- **WPS:** strict profile enabled (limits, magic numbers, complexity).
- **Renames (no collisions):** `B001`→`BAN001`, `C001`→`ORD001`, `D001`→`DEC001`, SQL→`SQL001` (bandit keeps `S`).

Status: **implemented** = shipped in MVP core; **planned** = catalog target for packs.

> **What's shipped today:** only the five rules in the *Implemented (MVP)* table
> below — `Q001`, `Q002`, `ORD001`, `BAN001`, `DEC001`. Everything in the
> flake8/Ruff-compatible, WPS, and CBP tables is **planned** (not yet
> implemented). Use [Ruff](with-ruff.md) for the standard families in the
> meantime.

---

## Implemented (MVP)

| Code | Rule |
|------|------|
| Q001 | Dict string literals → single quotes |
| Q002 | Message / raise / logging(/print) strings → double quotes |
| ORD001 | Configured call keyword-arg order |
| BAN001 | Configured banned calls (`eval`/`exec` by default) |
| DEC001 | Required decorators on named functions |

---

## flake8 / Ruff-compatible families (planned, same codes)

Default select draft:

`F,E,W,I,N,UP,B,SIM,C4,A,PIE,RET,T20,T10,TID,C901` + WPS + CBP below.

Default ignore draft: `D` (docstrings; project rarely wants them), global `Q` (use Q001/Q002), optional `E501` if formatter owns line length.

| Family | Codes | Notes |
|--------|-------|-------|
| Pyflakes | F | unused, undefined, F403 star-import |
| pycodestyle | E, W | style / whitespace |
| isort | I | import sorting |
| pep8-naming | N | names |
| pydocstyle | D | ignore by default for CBP services |
| pyupgrade | UP | modern syntax |
| bugbear | B | B006 mutable default, B001 empty `except`, … |
| simplify | SIM | |
| comprehensions | C4 | |
| builtins | A | shadowing |
| pie | PIE | |
| return | RET | |
| print | T20 | overlaps WPS421 / L002 |
| debugger | T10 | `breakpoint` / pdb |
| errmsg | EM | |
| tidy-imports | TID | |
| type-checking | TC / TCH | |
| bandit | S | security; **not** SQL001 |
| McCabe | C901 | cyclomatic; overlaps WPS2xx |
| Ruff-only | RUF | no quote rules |
| pylint-subset | PL | PLR/PLC/PLE useful subset |

---

## WPS strict (planned)

Enable full **WPS** in the strict profile; relax via `ignore` / per-file ignores.

| Group | Codes | Focus |
|-------|-------|-------|
| Naming | WPS11x–WPS12x | name length, underscores, … |
| Complexity | WPS2xx | too many args/returns/awaits, cognitive/Jones, nested defs, overused exprs |
| Consistency | WPS3xx | imports, multiline, return/yield consistency |
| Best practices | WPS4xx | magic numbers, `print`/`eval`/`exec`, `getattr`/`hasattr`, … |
| Refactoring | WPS5xx | useless lambda, simplify |
| OOP | WPS6xx | bases, slots misuse, … |

Known dual-codes (both kept under policy 2C; disable one in config if noisy):

| Topic | Ruff/flake8 | WPS |
|-------|-------------|-----|
| print | T201 | WPS421 |
| import * | F403 | WPS347 |
| complexity | C901 | WPS2xx |
| mutable default | B006 | WPS related |
| eval/exec | S102 / … | WPS421 |

---

## CBP / `.mdc` context rules (planned unless noted)

| Code | Rule | Source |
|------|------|--------|
| Q001 | dict → single quotes | **implemented** · python.mdc |
| Q002 | messages → double quotes | **implemented** · python.mdc |
| L001 | logger: message only via `msg=` | logging.mdc |
| L002 | no `print` | alias of T20/WPS — prefer T20, ignore L002 if both on |
| L003 | no `basicConfig` / `dictConfig` | logging.mdc |
| L004 | no nested `extra={'tags':…}` | logging.mdc |
| L005 | `logging.getLogger(__name__)` | logging.mdc |
| A001 | no `asyncio.get_event_loop()` | python.mdc |
| A002 | no `asyncio.to_thread` | python.mdc |
| A003 | no `requests` in async modules | graphql/python.mdc |
| A004 | `AppRunner(..., handle_signals=False)` | python.mdc |
| CFG001 | no `os.environ` outside `tests/` | project.mdc |
| CFG002 | settings fields need `Field(..., alias=…)` | project.mdc |
| CFG003 | `*_PASSWORD`/`*_SECRET`/keys → `SecretStr` | project.mdc |
| CFG004 | one `BaseSettings` + singleton per config file | python.mdc |
| E001 | no `raise Exception` / bare `BaseException` | db/s3.mdc |
| E002 | DAO must not call client `connect`/`close` | python.mdc |
| E003 | `__slots__` on infra/dao/manager classes | python.mdc |
| E004 | `app/dto/`: `msgspec.Struct, frozen=True` | python.mdc |
| G001 | ban graphene/ariadne/tartiflette/raw graphql schema | graphql.mdc |
| G002 | resolvers need `@observe_latency` | graphql.mdc |
| G003 | no DAO/SQL inside resolvers | graphql.mdc |
| SQL001 | no f-string / `.format` SQL in execute | db.mdc |
| S3G001 | no `gc` / `gc.collect` in s3/dao paths | s3.mdc |
| ORD001 | call keyword order | **implemented** |
| BAN001 | banned calls | **implemented** |
| DEC001 | required decorators | **implemented** |

---

## Suggested profiles

```toml
# Complement Ruff (recommended while packs are incomplete):
#   ruff check .          # F,E,W,I,UP,B,…
#   plintus check .   # Q001,Q002,ORD001,BAN001,DEC001 + future CBP/WPS

[tool.plintus]
select = ["Q001", "Q002", "ORD001", "BAN001", "DEC001"]
dict-quotes = "single"
message-quotes = "double"
banned-calls = ["eval", "exec"]

# Future “full” profile (when packs land):
# select = ["F", "E", "W", "I", "N", "UP", "B", "SIM", "C4", "A", "PIE", "RET",
#           "T20", "T10", "TID", "C901", "WPS", "Q001", "Q002",
#           "L", "A", "CFG", "E", "G", "SQL", "S3G", "ORD", "BAN", "DEC"]
# ignore = ["D", "Q000", "L002"]  # L002 if T20 enabled
```

## Using with Ruff today

See [with-ruff.md](with-ruff.md). Until F/E/W/… packs exist inside plintus, run **Ruff for standard families** and **plintus for Q/ORD/BAN/DEC (+ upcoming CBP)**.
