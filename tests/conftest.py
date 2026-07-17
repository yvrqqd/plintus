"""Shared pytest fixtures and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from plintus.config import Config
from plintus.engine import load_rules


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def cfg(**kwargs) -> Config:
    base = Config(cache=False, workers=1)
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


@pytest.fixture
def builtin_rules(cfg: Config):
    return load_rules(cfg)
