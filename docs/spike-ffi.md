# Spike notes: tree-sitter → normalized CST + FFI overhead

## Goal

Validate that wrapping tree-sitter nodes behind a stable handle API keeps
Python rule code simple while avoiding per-node FFI callbacks.

## Findings (design spike)

1. **Normalized handles win.** Exporting `(doc_id, node_id)` plus methods
   (`kind`, `text`, `parent`, `children`, `ancestors`) is enough for quote /
   call-context rules and lets us swap parsers later.
2. **Batch selection.** Rust walks the CST once, buckets node IDs by kind
   (`string`, `dictionary`, `call`, …). Python rules declare `targets` and
   receive only matching handles — one Python entry per rule/file.
3. **Expected overhead.** Crossing the FFI boundary per node is expensive;
   crossing once per rule with a `Vec<u32>` of node IDs is cheap. Benchmarks
   under `benchmarks/` measure parse/index vs rule execution separately.
4. **Quote literals need source text.** tree-sitter `string` nodes preserve
   quotes/prefixes; CPython `ast.Constant` does not. Confirms CST choice.

## Prototype surface used in MVP

```text
Document { path, source, nodes[], kind_index }
NodeHandle { doc, id } -> kind/start/end/text/parent/child/ancestors
analyze_file(path, source) -> Document
select(doc, kinds) -> [NodeHandle]
```
