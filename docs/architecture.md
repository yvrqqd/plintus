# Architecture Decision Record: plintus

## Status

Accepted for MVP (2026-07-17).

## Context

We need a fast Python linter that supports **complex, context-dependent rules**
(e.g. single quotes in dict literals, double quotes in message strings). Flake8
plugins are too slow and AST-limited; Ruff is extremely fast but does not expose
a stable third-party rule API. Rules like quote style require **lossless CST /
token information**, which CPython `ast` does not preserve.

## Options considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **tree-sitter + normalized API** | Lossless CST, error recovery, exact byte ranges, query prefilter | Untyped nodes need wrapping | **Chosen for MVP** |
| Ruff parser + token stream | Potentially fastest | Unstable crates, would need own CST layer | Deferred |
| LibCST (pure Python / native parser) | Excellent Python-first DX, perfect for autofix | Memory / traversal cost | Prototype only |
| Fork Ruff / Rude plugins | Faster time-to-market | No independent stable API / product differentiation | Rejected |

## Decision

1. **Rust core** parses with tree-sitter-python, builds a **normalized CST index**
   (`Document`, `Node`, `Span`) and never exports raw tree-sitter nodes.
2. **Python rules** run once per rule per file with a **lazy target selection**;
   no Rust→Python callback per CST node.
3. Ship as a **pip package** (maturin + PyO3): Python CLI + native extension.
4. Scope: **single-file CST + ancestor/sibling context** only. No import
   resolution, types, or project graph in MVP.
5. Complement Ruff: Ruff for standard rules; `plintus` for project policies.

## Performance principles (uv / Ruff-inspired)

- Content-addressed cache: `source hash + config hash + rule/API versions`
- Release GIL during Rust parse/index
- Stream files; process workers for Python rules above a file-count threshold
- Batch diagnostics/fixes across the FFI boundary

## Future (post-MVP)

- Native Rust rules for hot paths
- Declarative DSL (GritQL-like) for simple patterns
- Optional single-file scopes / project graph

## Operational notes (post-review)

### Document lifecycle

Documents are owned by a `#[pyclass] PyDocument` holding an `Arc<Document>`.
The CST (source + node array) is freed when the Python `Document` wrapper is
garbage-collected or when `close()` / the context manager exits. There is no
global document registry and no manual `drop_document` — this eliminates the
leak class where a forgotten `close()` would retain source + CST indefinitely.

### Cache key composition

`SHA-256(source || config_fingerprint || rules_hash || core_api_version)`.

- `config_fingerprint` excludes private fields (e.g. `_base_dir`) so the key
  is stable regardless of where the pyproject lives.
- `rules_hash` includes each rule's id, `api_version`, **and a hash of the
  rule's `check` source** — so editing rule logic without bumping
  `api_version` correctly invalidates the cache.
- Cache keys are validated to be hex digests before being joined to the cache
  dir, preventing path traversal via the FFI `cache_read`/`cache_write` entry
  points.

### Worker constraints

Multiprocessing workers reconstruct rules from `plintus.rules.register`
(builtins) only. `local-rules` files and entry-point plugins are not picklable
across the process boundary, so when they are active `plintus` falls back
to single-process lint and prints a warning — this prevents the silent
diagnostic loss that would otherwise occur if non-builtin rules were dropped
in the worker path.

### Severity / exit-code policy

Only `error`-severity diagnostics fail the process (exit 1). `warning` /
`info` / `hint` report but exit 0. This lets CI treat style warnings as
non-blocking while policy rules (`BAN001`, `DEC001`) fail builds.
