"""Process-worker helpers for Python rules (GIL-friendly parallelism)."""

from __future__ import annotations

import os

from plintus.config import Config


def decide_workers(n_files: int, config: Config) -> int:
    """Return process count to use (1 = inline)."""
    if config.workers == 1:
        return 1
    if n_files < config.worker_threshold:
        return 1
    if config.workers > 0:
        return config.workers
    return min(32, os.cpu_count() or 2)
