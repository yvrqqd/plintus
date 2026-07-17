"""CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plintus import __version__
from plintus.api import Severity
from plintus.config import load_config
from plintus.engine import lint_paths


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plintus",
        description="Fast Python linter for complex context-dependent rules",
    )
    p.add_argument("--version", action="version", version=f"plintus {__version__}")
    sub = p.add_subparsers(dest="command")

    check = sub.add_parser("check", help="Lint files or directories")
    check.add_argument("paths", nargs="*", default=["."], help="Files or directories")
    check.add_argument("--fix", action="store_true", help="Apply safe fixes")
    check.add_argument("--unsafe", action="store_true", help="Also apply unsafe fixes")
    check.add_argument("--diff", action="store_true", help="Show diffs instead of writing")
    check.add_argument("--select", type=str, default=None, help="Comma-separated rule ids")
    check.add_argument("--ignore", type=str, default=None, help="Comma-separated rule ids")
    check.add_argument("--output-format", choices=("text", "json"), default="text")
    check.add_argument("--no-cache", action="store_true")
    check.add_argument("--workers", type=int, default=None)
    check.add_argument("--config", type=str, default=None)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "check":
        if args.unsafe and not (args.fix or args.diff):
            parser.error("--unsafe requires --fix or --diff")
        return cmd_check(args, parser)
    parser.error(f"unknown command {args.command}")
    return 2


def cmd_check(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    overrides: dict = {}
    if args.select:
        overrides["select"] = [s.strip() for s in args.select.split(",") if s.strip()]
    if args.ignore:
        overrides["ignore"] = [s.strip() for s in args.ignore.split(",") if s.strip()]
    if args.no_cache:
        overrides["cache"] = False
    if args.workers is not None:
        overrides["workers"] = args.workers

    config = load_config(
        config_path=Path(args.config) if args.config else None,
        cli_overrides=overrides or None,
    )

    diagnostics, fixed = lint_paths(
        args.paths,
        config,
        apply_fixes=bool(args.fix or args.diff),
        unsafe_fixes=bool(args.unsafe),
    )

    if args.diff:
        for path, new_source in fixed.items():
            old = Path(path).read_text(encoding="utf-8")
            _print_diff(path, old, new_source)
    elif args.fix:
        for path, new_source in fixed.items():
            Path(path).write_text(new_source, encoding="utf-8")

    if args.output_format == "json":
        print(json.dumps([d.to_dict() for d in diagnostics], indent=2))
    else:
        visible = [d for d in diagnostics if not d.applied]
        for d in visible:
            print(f"{d.path}:{d.line}:{d.col}: {d.rule_id} {d.message}")
        if visible:
            print(f"Found {len(visible)} issue(s)", file=sys.stderr)
        elif diagnostics:
            print(f"Fixed {len(diagnostics)} issue(s)", file=sys.stderr)
        else:
            print("All checks passed!", file=sys.stderr)

    # Only error-severity diagnostics that were not auto-fixed fail the process.
    return 1 if any(d.severity == Severity.ERROR and not d.applied for d in diagnostics) else 0


def _print_diff(path: str, old: str, new: str) -> None:
    import difflib

    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=path,
        tofile=path,
    )
    sys.stdout.writelines(diff)


if __name__ == "__main__":
    raise SystemExit(main())
