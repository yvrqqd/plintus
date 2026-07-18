# plintus rules catalog

Decisions locked in:

- **Quotes:** contextual only — `Q001` / `Q002` (not global flake8-quotes / Ruff `Q000`).
- **flake8/Ruff:** maximum code compatibility (`F`, `E`, `W`, `I`, … same IDs) — still run via **Ruff**, not plintus.
- **WPS:** clean-room port of wemake-python-styleguide **codes** (catalog lists all; only implemented/partial checkers are registered). Enabled by default with `select = ["ALL"]` / `ignore = []`; opt out with `ignore = ["WPS"]`, or select specific `WPS*` codes.
- **Renames (no collisions):** `B001`→`BAN001`, `C001`→`ORD001`, `D001`→`DEC001`, SQL→`SQL001` (bandit keeps `S`; use `S3G` for S3G001 — prefix `S` alone does not match `S3G*`).

Status: **implemented** = dedicated checker runs; **partial** = heuristic / best-effort (may miss cases); **planned** = catalogued but not registered until implemented.

> **What's shipped today:** MVP (`Q001`, `Q002`, `ORD001`, `BAN001`, `DEC001`),
> full **CBP** pack (`L*`, `A*`, `CFG*`, `E*`, `G*`, `SQL001`, `S3G001`), and a **WPS**
> pack with implemented/partial checkers registered (planned codes stay in the catalog
> only). Default `select` is `["ALL"]` with `ignore = []` — all registered rules
> (including WPS) are on; set `ignore = ["WPS"]` to keep MVP+CBP only.
> Use [Ruff](with-ruff.md) for standard F/E/W/… families.

---

## Implemented (MVP)

| Code   | Rule                                                      |
| ------ | --------------------------------------------------------- |
| Q001   | Dict / subscript strings (incl. `extra=` slots, `obj['k']`) → single quotes |
| Q002   | Message / raise / logging(/print) strings → double quotes                   |
| ORD001 | Configured call keyword-arg order                         |
| BAN001 | Configured banned calls (`eval`/`exec` by default)        |
| DEC001 | Required decorators on named functions                    |

---

## WPS (enabled by default; mix of implemented / partial / planned)

Clean-room CST port of [wemake-python-styleguide](https://wemake-python-styleguide.readthedocs.io/)
violation codes. Thresholds use wemake defaults (`max-arguments = 5`, …) — see
[configuration.md](configuration.md).

**Default:** all registered rules (`select = ["ALL"]`, `ignore = []`). Opt out of
WPS with `ignore = ["WPS"]` (only implemented/partial codes are registered).

Family prefixes: `"WPS"` (all registered), `"WPS1"` (naming), `"WPS2"` (complexity), …

### Dual-codes (policy 2C — both kept)

| Topic           | Ruff/flake8 / CBP | WPS         |
| --------------- | ----------------- | ----------- |
| print           | T201 / L002       | WPS421      |
| import *        | F403              | WPS347      |
| complexity      | C901              | WPS2xx      |
| mutable default | B006              | WPS404      |
| eval/exec       | S102 / BAN001     | WPS421      |
| bare Exception  | E001              | WPS454      |
| `__slots__`     | E003 / E005       | WPS607      |

Recommended when running Ruff + plintus:

```toml
[tool.plintus]
select = ["ALL"]
ignore = ["L002"]  # Ruff T20 owns print; WPS on by default
```

Opt out of WPS:

```toml
[tool.plintus]
select = ["ALL"]
ignore = ["WPS", "L002"]  # MVP+CBP only
```

## WPS inventory

Coverage by family (approximate):

| Family | Dedicated | Partial | Planned stubs |
| ------ | --------- | ------- | ------------- |
| System (WPS0xx) | 1 (WPS000 reserved) | — | — |
| Naming (WPS1xx) | 19 | — | — |
| Complexity (WPS2xx) | 39 | — | — |
| OOP (WPS6xx) | 18 | — | — |
| Consistency (WPS3xx) | 23 | — | 44 |
| Best practices (WPS4xx) | 43 | 7 | 32 |
| Refactoring (WPS5xx) | 17 | 2 | 18 |


### System (1 rules)

| Code | Rule | Status |
| ---- | ---- | ------ |
| WPS000 | Internal linting error (reserved; never emitted by rules) | implemented (reserved/no-op) |

### Naming (19 rules)

| Code | Rule | Status |
| ---- | ---- | ------ |
| WPS100 | Forbid blacklisted module names | implemented |
| WPS101 | Forbid magic module names | implemented |
| WPS102 | Forbid module names that do not match pattern | implemented |
| WPS110 | Forbid blacklisted variable names | implemented |
| WPS111 | Forbid short names | implemented |
| WPS112 | Forbid private name pattern | implemented |
| WPS113 | Forbid same alias as original in imports | implemented |
| WPS114 | Forbid underscored numbers in names | implemented |
| WPS115 | Require snake_case for class attributes | implemented |
| WPS116 | Forbid consecutive underscores in names | implemented |
| WPS117 | Forbid reserved self/cls/mcs as variables | implemented |
| WPS118 | Forbid long names | implemented |
| WPS119 | Forbid unicode names | implemented |
| WPS120 | Forbid unnecessary trailing underscore | implemented |
| WPS121 | Forbid using variables marked unused | implemented |
| WPS122 | Forbid explicit unused variables | implemented |
| WPS123 | Forbid unused variables with multiple underscores | implemented |
| WPS124 | Forbid unreadable names | implemented |
| WPS125 | Forbid shadowing builtins | implemented |

### Complexity (39 rules)

| Code | Rule | Status |
| ---- | ---- | ------ |
| WPS200 | Forbid modules with complex lines (Jones) | implemented |
| WPS201 | Forbid too many imports | implemented |
| WPS202 | Forbid too many module members | implemented |
| WPS203 | Forbid too many imported names | implemented |
| WPS204 | Forbid overused expressions | implemented |
| WPS210 | Forbid too many local variables | implemented |
| WPS211 | Forbid too many arguments | implemented |
| WPS212 | Forbid too many returns | implemented |
| WPS213 | Forbid too many expressions | implemented |
| WPS214 | Forbid too many methods | implemented |
| WPS215 | Forbid too many base classes | implemented |
| WPS216 | Forbid too many decorators | implemented |
| WPS217 | Forbid too many awaits | implemented |
| WPS218 | Forbid too many asserts | implemented |
| WPS219 | Forbid too deep access | implemented |
| WPS220 | Forbid too deep nesting | implemented |
| WPS221 | Forbid complex lines | implemented |
| WPS222 | Forbid too many conditions | implemented |
| WPS223 | Forbid too many elifs | implemented |
| WPS224 | Forbid too many fors in comprehension | implemented |
| WPS225 | Forbid too many except cases | implemented |
| WPS226 | Forbid overused string literals | implemented |
| WPS227 | Forbid too long output tuples | implemented |
| WPS228 | Forbid too long compares | implemented |
| WPS229 | Forbid too long try body | implemented |
| WPS230 | Forbid too many public attributes | implemented |
| WPS231 | Forbid high cognitive complexity | implemented |
| WPS232 | Forbid high average cognitive complexity | implemented |
| WPS233 | Forbid too long call chains | implemented |
| WPS234 | Forbid complex annotations | implemented |
| WPS235 | Forbid too many import-from members | implemented |
| WPS236 | Forbid too long tuple unpack | implemented |
| WPS237 | Forbid complex f-strings | implemented |
| WPS238 | Forbid too many raises | implemented |
| WPS239 | Forbid too many except exceptions | implemented |
| WPS240 | Forbid too many type params | implemented |
| WPS241 | Forbid too many match subjects | implemented |
| WPS242 | Forbid too many match cases | implemented |
| WPS243 | Forbid too long finally body | implemented |

### Consistency (67 rules)

| Code | Rule | Status |
| ---- | ---- | ------ |
| WPS300 | Forbid imports relative to the current folder. | implemented |
| WPS301 | Forbid imports like import os.path. | implemented |
| WPS302 | Forbid u string prefix. | implemented |
| WPS303 | Forbid underscores (_) in numbers. | implemented |
| WPS304 | Forbid partial floats like .05 or 23.. | implemented |
| WPS305 | Forbid f strings. | implemented |
| WPS306 | Forbid writing explicit object base class. | implemented |
| WPS307 | Forbid multiple if statements inside list comprehensions. | implemented |
| WPS308 | Forbid comparing between two literals. | planned |
| WPS309 | Forbid comparisons where the argument doesn't come first. | planned |
| WPS310 | Forbid uppercase X, O, B, and E in numbers. | planned |
| WPS311 | Forbid comparisons with multiple in checks. | planned |
| WPS312 | Forbid comparisons of a variable to itself. | implemented |
| WPS313 | Enforce separation of parenthesis from keywords with spaces. | planned |
| WPS314 | Forbid using if or match statements that use invalid conditionals. | planned |
| WPS315 | Forbid extra object in parent classes list. | planned |
| WPS316 | Forbid multiple assignment targets for context managers. | planned |
| WPS317 | Forbid incorrect indentation for parameters. | planned |
| WPS318 | Forbid extra indentation. | planned |
| WPS319 | Forbid brackets in the wrong position. | planned |
| WPS320 | Forbid multi-line function type annotations. | planned |
| WPS321 | Forbid uppercase string modifiers. | implemented |
| WPS322 | Forbid triple quotes for singleline strings. | implemented |
| WPS323 | Forbid % formatting on strings. | implemented |
| WPS324 | Enforce consistent return statements. | implemented |
| WPS325 | Enforce consistent yield statements. | implemented |
| WPS326 | Forbid implicit string concatenation. | implemented |
| WPS327 | Forbid meaningless continue in loops. | planned |
| WPS328 | Forbid meaningless nodes. | planned |
| WPS329 | Forbid meaningless except cases. | planned |
| WPS330 | Forbid unnecessary operators in your code. | planned |
| WPS331 | Forbid local variables that are only used in return statements. | planned |
| WPS332 | Forbid the use of the walrus operator (:=) in most cases. | implemented |
| WPS333 | Forbid implicit complex comparison expressions. | planned |
| WPS334 | Forbid reversed order complex comparison expressions. | planned |
| WPS335 | Forbid wrong for loop iter targets. | planned |
| WPS336 | Forbid explicit string concatenation in favour of .format method. | implemented |
| WPS337 | Forbid multiline conditions. | planned |
| WPS338 | Forbid incorrect order of methods inside a class. | planned |
| WPS339 | Forbid meaningless zeros. | planned |
| WPS340 | Forbid extra + signs in the exponent. | planned |
| WPS341 | Forbid letters as hex numbers. | planned |
| WPS342 | Forbid \\ escape sequences inside regular strings. | planned |
| WPS343 | Forbid uppercase complex number suffix. | planned |
| WPS344 | Forbid explicit division (or modulo) by zero. | implemented |
| WPS345 | Forbid meaningless math operations with 0 and 1. | planned |
| WPS346 | Forbid double minus operations. | planned |
| WPS347 | Forbid imports that may cause confusion outside of the module. | implemented |
| WPS348 | Forbid starting lines with a dot. | planned |
| WPS349 | Forbid redundant components in a subscript's slice. | planned |
| WPS350 | Enforce using augmented assign pattern. | implemented |
| WPS351 | Forbid unnecessary literals in your code. | planned |
| WPS352 | Forbid multiline loops. | planned |
| WPS353 | Forbid yield from with several nodes. | planned |
| WPS354 | Forbid consecutive yield expressions. | planned |
| WPS355 | Forbid useless blank lines before and after brackets. | planned |
| WPS356 | Forbid unnecessary iterable unpacking. | planned |
| WPS357 | Forbid using \r (carriage return) in line breaks. | planned |
| WPS358 | Forbid using float zeros: 0.0. | implemented |
| WPS359 | Forbids to unpack iterable objects to lists. | planned |
| WPS360 | Forbid the use of raw strings when there is no backslash in the str... | planned |
| WPS361 | Forbids inconsistent newlines in comprehensions. | planned |
| WPS362 | Forbid assignment to a subscript slice. | planned |
| WPS363 | Forbid raising SystemExit. | implemented |
| WPS364 | Forbid using not a in b instead of a not in b. | implemented |
| WPS365 | Some match statements can be simplified to if statements. | planned |
| WPS366 | Forbid meaningless boolean operations. | planned |

### Best practices (82 rules)

| Code | Rule | Status |
| ---- | ---- | ------ |
| WPS400 | Restrict various control (such as magic) comments. | implemented |
| WPS401 | Forbid empty doc comments (#:). | implemented |
| WPS402 | Forbid too many # noqa comments. | implemented |
| WPS403 | Forbid too many # pragma: no cover comments. | implemented |
| WPS404 | Forbid complex defaults. | implemented |
| WPS405 | Forbid anything other than ast.Name to define loop variables. | implemented |
| WPS406 | Forbid anything other than ast.Name to define contexts. | implemented |
| WPS407 | Forbid mutable constants on a module level. | implemented |
| WPS408 | Forbid using the same logical conditions in one expression. | implemented |
| WPS409 | Forbid heterogeneous operators in one comparison. | implemented |
| WPS410 | Forbid some module-level variables. | implemented |
| WPS411 | Forbid empty modules. | implemented |
| WPS412 | Forbid logic inside __init__ module. | implemented |
| WPS413 | Forbid __getattr__ and __dir__ module magic methods. | implemented |
| WPS414 | Forbid tuple unpacking with side-effects. | implemented |
| WPS415 | Forbid the same exception class in multiple except blocks. | implemented |
| WPS416 | Forbid yield keyword inside comprehensions. | implemented |
| WPS417 | Forbid duplicate items in hashes. | implemented |
| WPS418 | Forbid exceptions inherited from BaseException. | implemented |
| WPS419 | Forbid multiple returning paths with try / except case. | implemented |
| WPS420 | Forbid some python keywords. | implemented |
| WPS421 | Forbid calling some built-in functions. | implemented |
| WPS422 | Forbid __future__ imports. | implemented |
| WPS423 | Forbid NotImplemented exception. | implemented |
| WPS424 | Forbid BaseException exception. | implemented |
| WPS425 | Forbid booleans as non-keyword parameters. | implemented |
| WPS426 | Forbid lambda inside loops. | implemented |
| WPS427 | Forbid unreachable code. | implemented |
| WPS428 | Forbid statements that do nothing. | implemented |
| WPS429 | Forbid multiple assignments on the same line. | implemented |
| WPS430 | Forbid nested functions. | implemented |
| WPS431 | Forbid nested classes. | implemented |
| WPS432 | Forbid magic numbers. | implemented |
| WPS433 | Forbid imports nested in functions. | implemented |
| WPS434 | Forbid assigning a variable to itself. | implemented |
| WPS435 | Forbid multiplying lists. | implemented |
| WPS436 | Forbid importing protected modules. | implemented |
| WPS437 | Forbid protected attributes and methods. | implemented |
| WPS438 | Forbid raising StopIteration inside generators. | implemented |
| WPS439 | Forbid Unicode escape sequences in binary strings. | implemented |
| WPS440 | Forbid overlapping local and block variables. | planned |
| WPS441 | Forbid control variables after the block body. | planned |
| WPS442 | Forbid shadowing variables from outer scopes. | planned |
| WPS443 | Forbid explicit unhashable types of asset items and dict keys. | planned |
| WPS444 | Forbid explicit falsely-evaluated conditions with several keywords. | planned |
| WPS445 | Forbid incorrectly named keywords in starred dicts. | planned |
| WPS446 | Forbid approximate constants. | planned |
| WPS447 | Forbid using the alphabet as a string. | planned |
| WPS448 | Forbid incorrect order of except. | planned |
| WPS449 | Forbid float keys. | planned |
| WPS450 | Forbid importing protected objects from modules. | planned |
| WPS451 | Forbid positional only or / arguments. | partial |
| WPS452 | Forbid break and continue in a finally block. | partial |
| WPS453 | Forbid executing a file with shebang incorrectly set. | partial |
| WPS454 | Forbid raising Exception or BaseException. | implemented |
| WPS455 | Forbids using non-trivial expressions as a parameter for except. | planned |
| WPS456 | Forbids using float("NaN") construct to generate NaN. | partial |
| WPS457 | Forbids use of infinite while True: loops. | implemented |
| WPS458 | Forbids to import from already imported modules. | planned |
| WPS459 | Forbids comparisons with float and complex. | planned |
| WPS460 | Forbids to have single element destructuring. | planned |
| WPS461 | Forbids to use specific inline ignore violations. | implemented |
| WPS462 | Forbids direct usage of multiline strings. | planned |
| WPS463 | Forbids to have functions starting with get_ without returning a va... | planned |
| WPS464 | Forbid empty comments. | partial |
| WPS465 | Forbid comparisons between bitwise and boolean expressions. | planned |
| WPS466 | Forbid using complex grammar for using decorators. | planned |
| WPS467 | Forbid using a bare raise keyword outside of except. | partial |
| WPS468 | Forbid using a placeholder (_) with enumerate. | planned |
| WPS469 | Forbid raising an exception from itself. | planned |
| WPS470 | Forbid kwarg unpacking in class definition. | planned |
| WPS471 | Forbid consecutive slices. | planned |
| WPS472 | Forbid getting first element using unpacking. | planned |
| WPS473 | Limit empty lines in functions or methods body. | planned |
| WPS474 | Do not allow importing the same object under different aliases. | planned |
| WPS475 | Do not use problematic function parameters. | planned |
| WPS476 | Do not use await in for loop. | partial |
| WPS477 | Forbid using TypeVarTuple after a TypeVar with default. | planned |
| WPS478 | Forbid using non strict slice operations. | planned |
| WPS479 | Forbid using multi-line formatted string with single and double quo... | planned |
| WPS480 | Forbid using comments inside formatted strings. | planned |
| WPS481 | Found a leaking for loop in a class or module body. | planned |

### Refactoring (37 rules)

| Code | Rule | Status |
| ---- | ---- | ------ |
| WPS500 | Forbid`else` without`break` in a loop. | implemented |
| WPS501 | Forbid`finally` in`try` block without`except` block. | implemented |
| WPS502 | Forbid simplifiable`if` conditions. | implemented |
| WPS503 | Forbid useless`else` cases in returning functions. | implemented |
| WPS504 | Forbid negated conditions together with`else` clause. | implemented |
| WPS505 | Forbid nested`try` blocks. | implemented |
| WPS506 | Forbid useless proxy`lambda` expressions. | implemented |
| WPS507 | Forbid unpythonic zero-length compare. | implemented |
| WPS508 | Forbid`not` with compare expressions. | implemented |
| WPS509 | Forbid nesting ternary expressions in certain places. | implemented |
| WPS510 | Forbid`in` with static containers except`set` nodes. | implemented |
| WPS511 | Forbid multiple`isinstance` calls on the same variable. | planned |
| WPS512 | Forbid multiple`isinstance` calls with single-item tuples. | planned |
| WPS513 | Forbid implicit`elif` conditions. | planned |
| WPS514 | Forbid multiple equality comparisons with the same variable. | planned |
| WPS515 | Forbid`open()` without a context manager. | implemented |
| WPS516 | Forbid comparing types with`type()` function. | implemented |
| WPS517 | Forbid useless starred expressions. | planned |
| WPS518 | Forbid implicit`enumerate()` calls. | implemented |
| WPS519 | Forbid implicit`sum()` calls. | planned |
| WPS520 | Forbid comparing with explicit falsy constants. | implemented |
| WPS521 | Forbid comparing values with constants using`is` or`is not`. | implemented |
| WPS522 | Forbid implicit primitives in the form of`lambda` functions. | planned |
| WPS523 | Forbid unpythonic variable swaps. | partial |
| WPS524 | Forbid misrefactored self assignment. | planned |
| WPS525 | Forbid comparisons where`in` is compared with single item container. | planned |
| WPS526 | Forbid`yield` inside`for` loop instead of`yield from`. | planned |
| WPS527 | Require tuples as arguments for certain functions. | planned |
| WPS528 | Forbid implicit`.items()` iterator. | planned |
| WPS529 | Forbid implicit`.get()` dict method. | planned |
| WPS530 | Forbid implicit negative indexes. | planned |
| WPS531 | Forbid if statements that simply return booleans in functions or me... | implemented |
| WPS532 | Forbid ast.Is in ast.Compare.ops when it's size is not zero. | planned |
| WPS533 | Forbid having duplicate conditions in several`if`//`elif` branches. | planned |
| WPS534 | Forbid having useless ternary expressions. | planned |
| WPS535 | Forbid having duplicate`case` patterns. | partial |
| WPS536 | Forbid extra syntax around`match` like list, set, or dict. | planned |

### OOP (18 rules)

| Code | Rule | Status |
| ---- | ---- | ------ |
| WPS600 | Forbid subclassing lowercase builtins | implemented |
| WPS601 | Forbid shadowing class attributes with instance attributes | implemented |
| WPS602 | Forbid @staticmethod decorator | implemented |
| WPS603 | Forbid certain magic methods | implemented |
| WPS604 | Forbid incorrect nodes inside class definitions | implemented |
| WPS605 | Forbid methods without any arguments | implemented |
| WPS606 | Forbid non-class base classes | implemented |
| WPS607 | Forbid incorrect __slots__ definition | implemented |
| WPS608 | Forbid super() with parameters or outside methods | implemented |
| WPS609 | Forbid direct magic attribute access | implemented |
| WPS610 | Forbid certain async magic methods | implemented |
| WPS611 | Forbid yield inside certain magic methods | implemented |
| WPS612 | Forbid useless overwritten methods | implemented |
| WPS613 | Forbid super() with incorrect method access | implemented |
| WPS614 | Forbid descriptors on regular functions | implemented |
| WPS615 | Forbid getters and setters in objects | implemented |
| WPS616 | Forbid bare super() in buggy contexts | implemented |
| WPS617 | Forbid lambda assigned as attribute | implemented |

---

## CBP / `.mdc` context rules (**implemented**)

Family prefixes work in `select` / `ignore` (e.g. `"L"` enables `L001`…`L005`).

| Code   | Rule                                                  | Source                                                    |
| ------ | ----------------------------------------------------- | --------------------------------------------------------- |
| L001   | logger: message only via `msg=`                       | logging.mdc                                               |
| L002   | no `print`                                            | alias of T20 — prefer T20, `ignore = ["L002"]` if both on |
| L003   | no `basicConfig` / `dictConfig`                       | logging.mdc                                               |
| L004   | no nested `extra={'tags':…}`                          | logging.mdc                                               |
| L005   | `logging.getLogger(__name__)`                         | logging.mdc                                               |
| A001   | no `asyncio.get_event_loop()`                         | python.mdc                                                |
| A002   | no `asyncio.to_thread`                                | python.mdc                                                |
| A003   | no `requests` in async modules                        | graphql/python.mdc                                        |
| A004   | `web.AppRunner` / `aiohttp.web.AppRunner` / imported `AppRunner` need `handle_signals=False` | python.mdc |
| CFG001 | no `os.environ` / `from os import environ` outside `tests/` | project.mdc                                               |
| CFG002 | settings fields need `Field(..., alias=…)`            | project.mdc                                               |
| CFG003 | `*_PASSWORD`/`*_SECRET`/keys → `SecretStr`            | project.mdc                                               |
| CFG004 | one `BaseSettings` + singleton per `app/config/` file | python.mdc                                                |
| E001   | no `raise Exception` / bare `BaseException`           | db/s3.mdc                                                 |
| E002   | under `app/dao/`: no client `connect`/`close`         | python.mdc                                                |
| E003   | `__slots__` on `app/infra`/`app/dao` classes with `self.*` attrs | python.mdc |
| E004   | module starts with 2–3 `#` copyright lines, then one blank line | — |
| E005   | slotted classes: no `self.__dict__` / `vars(self)`    | python.mdc                                                |
| G001   | ban graphene/ariadne/tartiflette                      | graphql.mdc                                               |
| G002   | resolvers need `@observe_latency`                     | graphql.mdc                                               |
| G003   | no DAO/SQL inside resolvers                           | graphql.mdc                                               |
| SQL001 | no f-string / `.format` SQL in execute                | db.mdc                                                    |
| S3G001 | no `gc` / `gc.collect` in s3/dao paths                | s3.mdc                                                    |
| ORD001 | call keyword order                                    |                                                           |
| BAN001 | banned calls                                          |                                                           |
| DEC001 | required decorators                                   |                                                           |

---

## Suggested profiles

```toml
# Complement Ruff:
#   ruff check .
#   plintus check .

# Default (all registered rules, including WPS):
[tool.plintus]
select = ["ALL"]
dict-quotes = "single"
message-quotes = "double"
banned-calls = ["eval", "exec"]

# Opt out of WPS:
# ignore = ["WPS"]

# When Ruff T20 is enabled, drop the duplicate print rule:
# ignore = ["L002"]
```

## Using with Ruff today

See [with-ruff.md](with-ruff.md). Run **Ruff for standard families** and
**plintus for Q/ORD/BAN/DEC + CBP + WPS** (drop WPS via `ignore` if needed).
