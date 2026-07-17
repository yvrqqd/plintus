"""Configuration loading from pyproject.toml / CLI."""

from __future__ import annotations

import json
import tomllib

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RuleContextConfig:
    """Subset of :class:`Config` exposed to rules via ``RuleContext.config``.

    Typed (not ``dict[str, Any]``) so plugin authors get autocomplete and the
    engine cannot drift from :class:`Config` — both are derived from the same
    dataclass via :meth:`Config.to_rule_context`.

    Supports dict-style ``.get(key, default)`` and ``config[key]`` access so
    existing rules that treat ``ctx.config`` as a mapping keep working.
    """

    message_calls: list[str]
    dict_quotes: str
    message_quotes: str
    banned_calls: list[str]
    require_decorators: dict[str, list[str]]
    call_arg_order: dict[str, list[str]]

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError as e:
            raise KeyError(key) from e

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and hasattr(self, key)


@dataclass
class Config:
    select: list[str] = field(default_factory=lambda: ["Q001", "Q002", "ORD001", "BAN001", "DEC001"])
    ignore: list[str] = field(default_factory=list)
    workers: int = 0  # 0 = auto, 1 = disable, N = pool size
    worker_threshold: int = 32
    cache: bool = True
    cache_dir: str = ".plintus_cache"
    message_calls: list[str] = field(
        default_factory=lambda: [
            "print",
            "logging.info",
            "logging.warning",
            "logging.error",
            "logging.debug",
            "logging.critical",
            # short names match via final segment (web.json_response → json_response)
            "json_response",
            "web.json_response",
        ]
    )
    dict_quotes: str = "single"  # single | double
    message_quotes: str = "double"
    banned_calls: list[str] = field(default_factory=lambda: ["eval", "exec"])
    require_decorators: dict[str, list[str]] = field(default_factory=dict)
    # call name -> required keyword arg order (ORD001)
    call_arg_order: dict[str, list[str]] = field(default_factory=dict)
    local_rules: list[str] = field(default_factory=list)
    # Directory used to resolve relative local_rules paths (set by load_config
    # to the pyproject parent). Not part of the fingerprint.
    _base_dir: Path | None = field(default=None, repr=False, compare=False)

    def enabled(self, rule_id: str) -> bool:
        if rule_id in self.ignore:
            return False
        if not self.select:
            return True
        return rule_id in self.select or "ALL" in self.select

    def fingerprint(self) -> str:
        # Exclude private fields (leading underscore) like _base_dir so cache
        # keys stay stable regardless of where the pyproject lives.
        payload = {
            k: v for k, v in asdict(self).items() if not k.startswith("_")
        }
        return json.dumps(payload, sort_keys=True, default=str)

    def to_rule_context(self) -> RuleContextConfig:
        """Build the typed config bag handed to ``RuleContext``.

        Single source of truth — replaces the hand-written ``config_dict``
        that previously existed in both ``lint_source`` and
        ``_lint_with_workers`` and could drift from :class:`Config`.
        """
        return RuleContextConfig(
            message_calls=list(self.message_calls),
            dict_quotes=self.dict_quotes,
            message_quotes=self.message_quotes,
            banned_calls=list(self.banned_calls),
            require_decorators={k: list(v) for k, v in self.require_decorators.items()},
            call_arg_order={k: list(v) for k, v in self.call_arg_order.items()},
        )

    def __post_init__(self) -> None:
        if self.dict_quotes not in ("single", "double"):
            raise ValueError(f"dict_quotes must be 'single' or 'double', got {self.dict_quotes!r}")
        if self.message_quotes not in ("single", "double"):
            raise ValueError(
                f"message_quotes must be 'single' or 'double', got {self.message_quotes!r}"
            )
        if self.workers < 0:
            raise ValueError(f"workers must be >= 0 (0=auto, 1=disable, N=pool), got {self.workers}")
        if self.worker_threshold < 1:
            raise ValueError(f"worker_threshold must be >= 1, got {self.worker_threshold}")


def find_pyproject(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        candidate = p / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load_config(
    *,
    config_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> Config:
    cfg = Config()
    path = config_path or find_pyproject()
    if path and path.is_file():
        with path.open("rb") as f:
            data = tomllib.load(f)
        section = data.get("tool", {}).get("plintus", {})
        if section:
            cfg = _from_mapping(section)
        # Resolve relative local_rules against the pyproject parent dir.
        cfg._base_dir = path.parent
    if cli_overrides:
        cfg = _apply_overrides(cfg, cli_overrides)
    return cfg


def _from_mapping(m: dict[str, Any]) -> Config:
    cfg = Config()
    if "select" in m:
        cfg.select = list(m["select"])
    if "ignore" in m:
        cfg.ignore = list(m["ignore"])
    if "workers" in m:
        cfg.workers = int(m["workers"])
    if "worker-threshold" in m:
        cfg.worker_threshold = int(m["worker-threshold"])
    if "worker_threshold" in m:
        cfg.worker_threshold = int(m["worker_threshold"])
    if "cache" in m:
        cfg.cache = bool(m["cache"])
    if "cache-dir" in m:
        cfg.cache_dir = str(m["cache-dir"])
    if "cache_dir" in m:
        cfg.cache_dir = str(m["cache_dir"])
    if "message-calls" in m:
        cfg.message_calls = list(m["message-calls"])
    if "message_calls" in m:
        cfg.message_calls = list(m["message_calls"])
    if "dict-quotes" in m:
        cfg.dict_quotes = str(m["dict-quotes"])
    if "dict_quotes" in m:
        cfg.dict_quotes = str(m["dict_quotes"])
    if "message-quotes" in m:
        cfg.message_quotes = str(m["message-quotes"])
    if "message_quotes" in m:
        cfg.message_quotes = str(m["message_quotes"])
    if "banned-calls" in m:
        cfg.banned_calls = list(m["banned-calls"])
    if "banned_calls" in m:
        cfg.banned_calls = list(m["banned_calls"])
    if "require-decorators" in m:
        cfg.require_decorators = {str(k): list(v) for k, v in dict(m["require-decorators"]).items()}
    if "require_decorators" in m:
        cfg.require_decorators = {str(k): list(v) for k, v in dict(m["require_decorators"]).items()}
    if "call-arg-order" in m:
        cfg.call_arg_order = {str(k): list(v) for k, v in dict(m["call-arg-order"]).items()}
    if "call_arg_order" in m:
        cfg.call_arg_order = {str(k): list(v) for k, v in dict(m["call_arg_order"]).items()}
    if "local-rules" in m:
        cfg.local_rules = list(m["local-rules"])
    if "local_rules" in m:
        cfg.local_rules = list(m["local_rules"])
    return cfg


def _apply_overrides(cfg: Config, overrides: dict[str, Any]) -> Config:
    for key, value in overrides.items():
        if value is None:
            continue
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    return cfg
