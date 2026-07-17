"""Plugin loading and lint engine."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Sequence

from plintus import API_VERSION
from plintus.api import Diagnostic, Rule, RuleContext
from plintus.config import Config
from plintus.document import parse_file
from plintus import _core


def _diagnostic_sort_key(d: Diagnostic) -> tuple[Any, ...]:
    return (d.path, d.start, d.rule_id, d.message)


def _sort_diagnostics(diags: list[Diagnostic]) -> list[Diagnostic]:
    diags.sort(key=_diagnostic_sort_key)
    return diags


class PluginError(RuntimeError):
    pass


def load_rules(config: Config) -> list[Rule]:
    rules: list[Rule] = []

    # entry points
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        entry_points = None  # type: ignore

    plugin_rules: list[Rule] = []
    if entry_points is not None:
        eps = entry_points()
        if hasattr(eps, "select"):
            selected = eps.select(group="plintus.plugins")
        else:  # pragma: no cover - Python <3.10 style EntryPoints
            selected = eps.get("plintus.plugins", [])  # type: ignore[attr-defined]
        for ep in selected:
            loaded = ep.load()
            if callable(loaded):
                result = loaded()
                if isinstance(result, list):
                    plugin_rules.extend(result)
                elif isinstance(result, Rule):
                    plugin_rules.append(result)
            elif isinstance(loaded, list):
                plugin_rules.extend(loaded)

    # Always include builtins, then merge plugin rules on top. A minimal plugin
    # that only adds one rule must NOT silently disable Q001/BAN001/etc.
    from plintus.rules import register

    rules.extend(register())
    rules.extend(plugin_rules)

    for path in config.local_rules:
        rules.extend(_load_local_rules(path, base_dir=getattr(config, "_base_dir", None)))

    # dedupe by id, keep first (builtin wins over plugin on collision)
    seen: set[str] = set()
    unique: list[Rule] = []
    for r in rules:
        if not r.id:
            raise PluginError(f"rule without id: {r!r}")
        if getattr(r, "api_version", "1") != API_VERSION:
            raise PluginError(
                f"rule {r.id} requires API {getattr(r, 'api_version', '?')}, "
                f"plintus speaks {API_VERSION}"
            )
        if r.id in seen:
            continue
        seen.add(r.id)
        unique.append(r)

    return [r for r in unique if config.enabled(r.id)]


def _load_local_rules(path: str, *, base_dir: Path | None = None) -> list[Rule]:
    p = Path(path)
    # Resolve relative to the pyproject directory (base_dir) when given, so
    # `local-rules = ["rules.py"]` in pyproject.toml works regardless of cwd.
    if not p.is_absolute() and base_dir is not None:
        p = (base_dir / p)
    if not p.is_file():
        raise PluginError(f"local rules file not found: {path}")
    # Unique module name keyed by absolute path hash — avoids collisions when
    # two directories contain a file with the same stem (e.g. both `rules.py`).
    import hashlib

    abs_id = hashlib.sha1(str(p.resolve()).encode("utf-8")).hexdigest()[:12]
    mod_name = f"plintus_local_{abs_id}"
    spec = importlib.util.spec_from_file_location(mod_name, p)
    if spec is None or spec.loader is None:
        raise PluginError(f"cannot import local rules: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    if hasattr(mod, "register") and callable(mod.register):
        result = mod.register()
        return list(result)
    out: list[Rule] = []
    for value in vars(mod).values():
        if isinstance(value, type) and issubclass(value, Rule) and value is not Rule and value.id:
            out.append(value())
    return out


def rules_hash(rules: Sequence[Rule]) -> str:
    """Hash rule identity AND implementation so changing rule logic without
    bumping ``api_version`` invalidates the cache (prevents stale diagnostics)."""
    import inspect

    parts: list[str] = []
    for r in sorted(rules, key=lambda x: x.id):
        impl_hash = ""
        check = getattr(type(r), "check", None)
        if check is not None:
            try:
                impl_hash = _core.hash_text(inspect.getsource(check))
            except (OSError, TypeError):
                # Source unavailable (e.g. frozen, C-defined) — fall back to qualname.
                impl_hash = f"{type(r).__module__}.{type(r).__qualname__}.{check.__qualname__}"
        parts.append(f"{r.id}:{getattr(r, 'api_version', '1')}:{impl_hash}")
    return _core.hash_text("|".join(parts) + f"|core:{_core.api_version()}")


def lint_source(
    path: str,
    source: str,
    rules: Sequence[Rule],
    config: Config,
    *,
    use_cache: bool | None = None,
) -> list[Diagnostic]:
    use_cache = config.cache if use_cache is None else use_cache
    cfg_hash = _core.hash_text(config.fingerprint())
    r_hash = rules_hash(rules)
    key = _core.make_cache_key(source, cfg_hash, r_hash)

    if use_cache:
        cached = _core.cache_read(config.cache_dir, key)
        if cached is not None:
            try:
                data = json.loads(cached)
            except (json.JSONDecodeError, ValueError):
                data = None
            if data is not None:
                return [_diagnostic_from_dict(d) for d in data]
            # Corrupt cache file — treat as miss; the fresh payload written
            # below overwrites it.

    doc, _micros = parse_file(path, source)
    try:
        diagnostics: list[Diagnostic] = []
        rule_config = config.to_rule_context()
        for rule in rules:
            kinds = list(rule.targets) if rule.targets else []
            nodes = doc.select(kinds) if kinds else doc.select_all()
            ctx = RuleContext(doc, nodes, rule, rule_config)
            rule.check(ctx)
            diagnostics.extend(ctx.diagnostics())
    finally:
        doc.close()

    diagnostics.sort(key=_diagnostic_sort_key)

    if use_cache:
        payload = json.dumps([d.to_dict() for d in diagnostics])
        _core.cache_write(config.cache_dir, key, payload)

    return diagnostics


def lint_file(path: str, rules: Sequence[Rule], config: Config) -> list[Diagnostic]:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return lint_source(path, source, rules, config)


def _diagnostic_from_dict(d: dict[str, Any]) -> Diagnostic:
    from typing import cast

    from plintus.api import Fix, SafetyLevel, Severity

    fix = None
    if "fix" in d and d["fix"] is not None:
        fd = d["fix"]
        safety = str(fd.get("safety", "safe"))
        if safety not in ("safe", "unsafe"):
            safety = "safe"
        fix = Fix(
            start=int(fd["start"]),
            end=int(fd["end"]),
            replacement=str(fd["replacement"]),
            safety=cast(SafetyLevel, safety),
        )
    return Diagnostic(
        rule_id=str(d["rule_id"]),
        message=str(d["message"]),
        path=str(d["path"]),
        start=int(d["start"]),
        end=int(d["end"]),
        line=int(d["line"]),
        col=int(d["col"]),
        severity=Severity(d.get("severity", "error")),
        fix=fix,
        applied=bool(d.get("applied", False)),
    )


def _worker_lint_file(args: tuple[str, list[str], dict[str, Any]]) -> list[dict[str, Any]]:
    """Picklable worker entry: reconstruct config/rules by id from builtins + config."""
    path, rule_ids, config_dict = args
    from plintus.config import Config
    from plintus.rules import register

    config = Config(**{k: v for k, v in config_dict.items() if k in Config.__dataclass_fields__})
    all_rules = {r.id: r for r in register()}
    # local rules not supported in workers for MVP unless already importable
    rules = [all_rules[i] for i in rule_ids if i in all_rules]
    diags = lint_file(path, rules, config)
    return [d.to_dict() for d in diags]


def lint_paths(
    paths: Sequence[str],
    config: Config,
    *,
    apply_fixes: bool = False,
    unsafe_fixes: bool = False,
) -> tuple[list[Diagnostic], dict[str, str]]:
    """Lint paths. Returns diagnostics and map of path -> fixed source (if any)."""
    from plintus.document import discover

    files = discover(list(paths) if paths else ["."])
    rules = load_rules(config)
    rule_ids = [r.id for r in rules]

    diagnostics: list[Diagnostic] = []
    fixed_sources: dict[str, str] = {}

    use_workers = _should_use_workers(len(files), config) and _workers_safe_for(rules, config)
    if use_workers and not apply_fixes:
        diagnostics = _lint_with_workers(files, rule_ids, config)
    else:
        for path in files:
            diags = lint_file(path, rules, config)
            if apply_fixes:
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                new_source, diags = apply_diagnostics_fixes(source, diags, unsafe=unsafe_fixes)
                if new_source != source:
                    fixed_sources[path] = new_source
            diagnostics.extend(diags)

    diagnostics.sort(key=_diagnostic_sort_key)
    return diagnostics, fixed_sources


def _workers_safe_for(rules: Sequence[Rule], config: Config) -> bool:
    """Workers only know how to reconstruct builtin rules (via ``register()``).
    Local-rule files and entry-point plugins are not picklable across the
    process boundary, so silently fall back to inline to avoid dropping
    diagnostics (P1 bug). Emits a warning so users notice the slowdown.
    """
    if config.local_rules:
        import sys

        print(
            "warning: local-rules are not supported in worker processes; "
            "falling back to single-process lint",
            file=sys.stderr,
        )
        return False
    from plintus.rules import register

    builtin_ids = {r.id for r in register()}
    for r in rules:
        if r.id not in builtin_ids:
            import sys

            print(
                "warning: non-builtin rule %r is not supported in worker processes; "
                "falling back to single-process lint" % r.id,
                file=sys.stderr,
            )
            return False
    return True


def _should_use_workers(n_files: int, config: Config) -> bool:
    from plintus.workers import decide_workers

    return decide_workers(n_files, config) > 1


def _lint_with_workers(files: list[str], rule_ids: list[str], config: Config) -> list[Diagnostic]:
    from dataclasses import asdict

    from plintus.workers import decide_workers

    workers = decide_workers(len(files), config)
    # Workers reconstruct a Config from this dict. We drop local_rules because
    # _workers_safe_for already guaranteed only builtin rules are active here.
    config_dict = asdict(config)
    config_dict["local_rules"] = []
    config_dict["workers"] = 1  # avoid nested worker pools inside a worker
    args_list = [(f, rule_ids, config_dict) for f in files]
    out: list[Diagnostic] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_worker_lint_file, a) for a in args_list]
        for fut in as_completed(futures):
            try:
                for d in fut.result():
                    out.append(_diagnostic_from_dict(d))
            except Exception as e:
                # Attach file-path context so a worker crash doesn't surface as
                # an opaque concurrent.futures exception.
                raise RuntimeError(f"worker lint failed: {e}") from e
    return out


def apply_diagnostics_fixes(
    source: str,
    diagnostics: list[Diagnostic],
    *,
    unsafe: bool = False,
) -> tuple[str, list[Diagnostic]]:
    """Apply non-overlapping fixes from end to start.

    Returns ``(new_source, all_diagnostics)`` where each diagnostic carries an
    ``applied`` flag: ``True`` if its fix was applied, ``False`` if it had no
    fix, was unsafe (without ``unsafe``), or was skipped due to overlap.

    Spans are UTF-8 byte offsets (tree-sitter); edits are applied on encoded bytes.
    """
    fixes: list[tuple[Diagnostic, Any]] = []
    for d in diagnostics:
        d.applied = False
        if d.fix is None:
            continue
        if d.fix.safety != "safe" and not unsafe:
            continue
        fixes.append((d, d.fix))

    # sort by start desc, skip overlaps
    fixes.sort(key=lambda x: x[1].start, reverse=True)
    applied_ranges: list[tuple[int, int]] = []
    data = bytearray(source.encode("utf-8"))
    for d, fix in fixes:
        if any(not (fix.end <= a or fix.start >= b) for a, b in applied_ranges):
            continue
        replacement = fix.replacement.encode("utf-8")
        data[fix.start : fix.end] = replacement
        applied_ranges.append((fix.start, fix.end))
        d.applied = True
    return data.decode("utf-8"), diagnostics
