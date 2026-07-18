"""Path helpers for path-scoped CBP rules."""

from __future__ import annotations

from pathlib import PurePosixPath


def norm_parts(path: str) -> tuple[str, ...]:
    """Normalize a file path to lowercase posix parts."""
    p = path.replace("\\", "/").lower()
    return tuple(PurePosixPath(p).parts)


def path_has_segment(path: str, segment: str) -> bool:
    return segment in norm_parts(path)


def path_under(path: str, *markers: str) -> bool:
    """True if path contains the consecutive marker segments (e.g. ``app``, ``dao``)."""
    parts = norm_parts(path)
    if len(markers) > len(parts):
        return False
    n = len(markers)
    for i in range(len(parts) - n + 1):
        if parts[i : i + n] == markers:
            return True
    return False


def is_test_path(path: str) -> bool:
    return path_has_segment(path, "tests") or path_has_segment(path, "test")


def is_graphql_resolver_path(path: str) -> bool:
    parts = norm_parts(path)
    if "graphql" not in parts:
        return False
    name = parts[-1] if parts else ""
    # Wiring / transport modules — not resolvers
    if name in ("extensions.py", "context.py", "server.py", "graphql_view.py"):
        return False
    return True
