#!/usr/bin/env python3
"""Reproducible micro-benchmarks for plintus phases.

Measures: discovery, parse/index, rule execution, cold/warm cache, and
optionally compares against Ruff/Flake8 if installed.

Methodology notes:
- `timed()` discards the first run as warmup and reports median + min/max/stdev.
- "cache-miss (modified source)" is a true miss: the source is changed each
  call so the cache key differs from any prior entry.
- `--workers N` controls multiprocessing for the all-files lint (0 = auto).
- The corpus triggers every selected rule (Q001/Q002/BAN001/ORD001/DEC001).
- External-tool comparison uses the same `timed()` median (no warmup discard
  for one-shot external runs is intentional — they pay their own startup).
- A baseline JSON can be written with --baseline and compared with --check.
"""

from __future__ import annotations

import argparse
import atexit
import json
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from plintus.config import Config
from plintus.document import discover, parse_file
from plintus.engine import lint_paths, lint_source, load_rules


def make_corpus(n_files: int, lines: int) -> Path:
    root = Path(tempfile.mkdtemp(prefix="plintus_bench_"))
    # Generate code that triggers every selected rule:
    #   - dict with double-quoted keys/values  (Q001)
    #   - print/raise with single-quoted msgs   (Q002)
    #   - eval                                   (BAN001)
    #   - misordered client.request kwargs       (ORD001)
    #   - undecorated handle_event               (DEC001)
    for i in range(n_files):
        body = [
            "from app import client",
            "def login_required(f):",
            "    return f",
            "",
        ]
        for j in range(lines):
            body.append(f"d{j} = {{'k{j}': \"v{j}\", \"x\": 'y'}}")
            body.append(f"print('msg{j}')")
            body.append(f"raise ValueError('e{j}')")
        body.append('eval("x")')
        body.append('client.request(timeout=1, method="GET", url="/")')
        body.append("def handle_event(data):")
        body.append("    return data")
        (root / f"f{i:04d}.py").write_text("\n".join(body) + "\n", encoding="utf-8")
    return root


def _cleanup(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def timed(fn, repeats: int = 5, *, discard_warmup: bool = True) -> list[float]:
    samples = []
    total = repeats + (1 if discard_warmup else 0)
    for i in range(total):
        t0 = time.perf_counter()
        fn()
        dt = time.perf_counter() - t0
        if discard_warmup and i == 0:
            continue
        samples.append(dt)
    return samples


def fmt(samples: list[float]) -> str:
    med = statistics.median(samples) * 1000
    if len(samples) >= 2:
        return (
            f"median={med:.2f}ms min={min(samples)*1000:.2f}ms "
            f"max={max(samples)*1000:.2f}ms stdev={statistics.stdev(samples)*1000:.2f}ms"
        )
    return f"median={med:.2f}ms"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=50)
    ap.add_argument("--lines", type=int, default=40)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--workers", type=int, default=1, help="0=auto for all-files lint")
    ap.add_argument("--baseline", type=str, default=None, help="write results JSON to this path")
    ap.add_argument("--check", type=str, default=None, help="compare against baseline JSON")
    args = ap.parse_args()

    root = make_corpus(args.files, args.lines)
    atexit.register(_cleanup, root)
    print(f"corpus: {root} ({args.files} files, ~{args.lines*3 + 8} lines each)")

    paths = discover([str(root)])
    disc = timed(lambda: discover([str(root)]), args.repeats)
    print(f"discovery: {fmt(disc)}")

    sample = Path(paths[0]).read_text(encoding="utf-8")

    def parse_one():
        doc, _ = parse_file(paths[0], sample)
        doc.close()

    parse_s = timed(parse_one, args.repeats)
    print(f"parse+index (1 file): {fmt(parse_s)}")

    cfg = Config(
        cache=False, workers=1,
        select=["Q001", "Q002", "BAN001", "ORD001", "DEC001"],
        call_arg_order={"client.request": ["method", "url", "timeout"]},
        require_decorators={"handle_event": ["login_required"]},
    )
    rules = load_rules(cfg)

    def lint_one():
        lint_source(paths[0], sample, rules, cfg, use_cache=False)

    lint_s = timed(lint_one, args.repeats)
    print(f"lint rules (1 file, no cache): {fmt(lint_s)}")

    cache_dir = root / ".cache"
    cfg_c = Config(
        cache=True, cache_dir=str(cache_dir), workers=1,
        select=["Q001", "Q002", "BAN001"],
    )
    rules_c = load_rules(cfg_c)
    lint_source(paths[0], sample, rules_c, cfg_c, use_cache=True)  # warm fill

    # True cache miss: modify source so the key differs from any prior entry.
    miss_counter = [0]

    def lint_miss():
        miss_counter[0] += 1
        lint_source(paths[0], sample + f" # {miss_counter[0]}\n", rules_c, cfg_c, use_cache=True)

    miss_s = timed(lint_miss, args.repeats, discard_warmup=False)
    print(f"cache-miss (modified source): {fmt(miss_s)}")

    warm_s = timed(lambda: lint_source(paths[0], sample, rules_c, cfg_c, use_cache=True), args.repeats)
    print(f"cache-warm (hit): {fmt(warm_s)}")

    # All-files lint: inline vs workers
    cfg_all_inline = Config(
        cache=False, workers=1,
        select=["Q001", "Q002", "BAN001", "ORD001", "DEC001"],
        call_arg_order={"client.request": ["method", "url", "timeout"]},
        require_decorators={"handle_event": ["login_required"]},
        worker_threshold=2,
    )

    def lint_all_inline():
        diags, _ = lint_paths(paths, cfg_all_inline)
        return len(diags)

    all_inline_s = timed(lint_all_inline, max(1, args.repeats // 2))
    print(f"lint all ({len(paths)} files, inline, no cache): {fmt(all_inline_s)}")

    if args.workers != 1:
        cfg_all_par = Config(
            cache=False, workers=args.workers,
            select=["Q001", "Q002", "BAN001", "ORD001", "DEC001"],
            call_arg_order={"client.request": ["method", "url", "timeout"]},
            require_decorators={"handle_event": ["login_required"]},
            worker_threshold=2,
        )

        def lint_all_par():
            diags, _ = lint_paths(paths, cfg_all_par)
            return len(diags)

        all_par_s = timed(lint_all_par, max(1, args.repeats // 2))
        print(f"lint all ({len(paths)} files, workers={args.workers}, no cache): {fmt(all_par_s)}")

    # optional external tools
    for tool, cmd in [
        ("ruff", ["ruff", "check", str(root)]),
        ("flake8", ["flake8", str(root)]),
    ]:
        if shutil.which(cmd[0]):
            ext_s = timed(lambda: subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), 1, discard_warmup=False)
            print(f"compare {tool}: {fmt(ext_s)} (installed; different ruleset — not directly comparable)")
        else:
            print(f"compare {tool}: not installed")

    if args.baseline:
        results = {
            "discovery_ms": statistics.median(disc) * 1000,
            "parse_index_ms": statistics.median(parse_s) * 1000,
            "lint_one_ms": statistics.median(lint_s) * 1000,
            "cache_miss_ms": statistics.median(miss_s) * 1000,
            "cache_warm_ms": statistics.median(warm_s) * 1000,
            "lint_all_inline_ms": statistics.median(all_inline_s) * 1000,
            "files": args.files,
            "lines": args.lines,
        }
        Path(args.baseline).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written: {args.baseline}")

    if args.check:
        prev = json.loads(Path(args.check).read_text(encoding="utf-8"))
        cur_med = statistics.median(all_inline_s) * 1000
        prev_med = prev.get("lint_all_inline_ms", cur_med)
        ratio = cur_med / prev_med if prev_med else 1.0
        print(f"regression check: current={cur_med:.2f}ms baseline={prev_med:.2f}ms ratio={ratio:.2f}x")


if __name__ == "__main__":
    main()
