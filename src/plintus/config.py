"""Configuration loading from pyproject.toml / CLI."""

from __future__ import annotations

import json
import tomllib

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _default_nested_classes_whitelist() -> list[str]:
    return ["Meta", "Params", "Config"]


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
    # WPS thresholds (wemake defaults)
    min_name_length: int = 2
    max_name_length: int = 45
    nested_classes_whitelist: list[str] = field(
        default_factory=_default_nested_classes_whitelist
    )
    max_noqa_comments: int = 10
    allowed_domain_names: list[str] = field(default_factory=list)
    forbidden_domain_names: list[str] = field(default_factory=list)
    allowed_module_metadata: list[str] = field(default_factory=list)
    forbidden_module_metadata: list[str] = field(default_factory=list)
    forbidden_inline_ignore: list[str] = field(default_factory=list)
    exps_for_one_empty_line: int = 2
    known_enum_bases: list[str] = field(default_factory=list)
    max_returns: int = 5
    max_local_variables: int = 5
    max_expressions: int = 9
    max_arguments: int = 5
    max_module_members: int = 7
    max_methods: int = 7
    max_line_complexity: int = 14
    max_jones_score: int = 12
    max_imports: int = 12
    max_imported_names: int = 50
    max_base_classes: int = 3
    max_decorators: int = 5
    max_string_usages: int = 3
    max_awaits: int = 5
    max_try_body_length: int = 1
    max_module_expressions: int = 7
    max_function_expressions: int = 4
    max_asserts: int = 5
    max_access_level: int = 4
    max_attributes: int = 6
    max_raises: int = 3
    max_except_exceptions: int = 3
    max_cognitive_score: int = 12
    max_cognitive_average: int = 8
    max_call_level: int = 3
    max_annotation_complexity: int = 3
    max_import_from_members: int = 8
    max_tuple_unpack_length: int = 4
    max_type_params: int = 6
    max_match_subjects: int = 7
    max_match_cases: int = 7
    max_lines_in_finally: int = 2
    max_conditions: int = 4
    known_first_party: list[str] = field(default_factory=lambda: ["app"])
    cbp_import_prefix: str = "cbp_"

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
    select: list[str] = field(default_factory=lambda: ["ALL"])
    # All registered rules enabled by default (including WPS); use ignore to opt out.
    ignore: list[str] = field(default_factory=list)
    # Path prefixes relative to cwd (e.g. "tests/fixtures") skipped during discovery.
    exclude: list[str] = field(default_factory=list)
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
    # WPS thresholds
    min_name_length: int = 2
    max_name_length: int = 45
    nested_classes_whitelist: list[str] = field(
        default_factory=_default_nested_classes_whitelist
    )
    max_noqa_comments: int = 10
    allowed_domain_names: list[str] = field(default_factory=list)
    forbidden_domain_names: list[str] = field(default_factory=list)
    allowed_module_metadata: list[str] = field(default_factory=list)
    forbidden_module_metadata: list[str] = field(default_factory=list)
    forbidden_inline_ignore: list[str] = field(default_factory=list)
    exps_for_one_empty_line: int = 2
    known_enum_bases: list[str] = field(default_factory=list)
    max_returns: int = 5
    max_local_variables: int = 5
    max_expressions: int = 9
    max_arguments: int = 5
    max_module_members: int = 7
    max_methods: int = 7
    max_line_complexity: int = 14
    max_jones_score: int = 12
    max_imports: int = 12
    max_imported_names: int = 50
    max_base_classes: int = 3
    max_decorators: int = 5
    max_string_usages: int = 3
    max_awaits: int = 5
    max_try_body_length: int = 1
    max_module_expressions: int = 7
    max_function_expressions: int = 4
    max_asserts: int = 5
    max_access_level: int = 4
    max_attributes: int = 6
    max_raises: int = 3
    max_except_exceptions: int = 3
    max_cognitive_score: int = 12
    max_cognitive_average: int = 8
    max_call_level: int = 3
    max_annotation_complexity: int = 3
    max_import_from_members: int = 8
    max_tuple_unpack_length: int = 4
    max_type_params: int = 6
    max_match_subjects: int = 7
    max_match_cases: int = 7
    max_lines_in_finally: int = 2
    max_conditions: int = 4
    known_first_party: list[str] = field(default_factory=lambda: ["app"])
    cbp_import_prefix: str = "cbp_"
    # Directory used to resolve relative local_rules paths (set by load_config
    # to the pyproject parent). Not part of the fingerprint.
    _base_dir: Path | None = field(default=None, repr=False, compare=False)

    def enabled(self, rule_id: str) -> bool:
        if _matches_any(rule_id, self.ignore):
            return False
        if not self.select:
            return True
        if "ALL" in self.select:
            return True
        return _matches_any(rule_id, self.select)

    def fingerprint(self) -> str:
        # Exclude private fields (leading underscore) like _base_dir so cache
        # keys stay stable regardless of where the pyproject lives.
        payload = {
            k: v for k, v in asdict(self).items() if not k.startswith("_")
        }
        return json.dumps(payload, sort_keys=True, default=str)

    def to_rule_context(self) -> RuleContextConfig:
        """Build the typed config bag handed to ``RuleContext``."""
        return RuleContextConfig(
            message_calls=list(self.message_calls),
            dict_quotes=self.dict_quotes,
            message_quotes=self.message_quotes,
            banned_calls=list(self.banned_calls),
            require_decorators={k: list(v) for k, v in self.require_decorators.items()},
            call_arg_order={k: list(v) for k, v in self.call_arg_order.items()},
            min_name_length=self.min_name_length,
            max_name_length=self.max_name_length,
            nested_classes_whitelist=list(self.nested_classes_whitelist),
            max_noqa_comments=self.max_noqa_comments,
            allowed_domain_names=list(self.allowed_domain_names),
            forbidden_domain_names=list(self.forbidden_domain_names),
            allowed_module_metadata=list(self.allowed_module_metadata),
            forbidden_module_metadata=list(self.forbidden_module_metadata),
            forbidden_inline_ignore=list(self.forbidden_inline_ignore),
            exps_for_one_empty_line=self.exps_for_one_empty_line,
            known_enum_bases=list(self.known_enum_bases),
            max_returns=self.max_returns,
            max_local_variables=self.max_local_variables,
            max_expressions=self.max_expressions,
            max_arguments=self.max_arguments,
            max_module_members=self.max_module_members,
            max_methods=self.max_methods,
            max_line_complexity=self.max_line_complexity,
            max_jones_score=self.max_jones_score,
            max_imports=self.max_imports,
            max_imported_names=self.max_imported_names,
            max_base_classes=self.max_base_classes,
            max_decorators=self.max_decorators,
            max_string_usages=self.max_string_usages,
            max_awaits=self.max_awaits,
            max_try_body_length=self.max_try_body_length,
            max_module_expressions=self.max_module_expressions,
            max_function_expressions=self.max_function_expressions,
            max_asserts=self.max_asserts,
            max_access_level=self.max_access_level,
            max_attributes=self.max_attributes,
            max_raises=self.max_raises,
            max_except_exceptions=self.max_except_exceptions,
            max_cognitive_score=self.max_cognitive_score,
            max_cognitive_average=self.max_cognitive_average,
            max_call_level=self.max_call_level,
            max_annotation_complexity=self.max_annotation_complexity,
            max_import_from_members=self.max_import_from_members,
            max_tuple_unpack_length=self.max_tuple_unpack_length,
            max_type_params=self.max_type_params,
            max_match_subjects=self.max_match_subjects,
            max_match_cases=self.max_match_cases,
            max_lines_in_finally=self.max_lines_in_finally,
            max_conditions=self.max_conditions,
            known_first_party=list(self.known_first_party),
            cbp_import_prefix=self.cbp_import_prefix,
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


def _matches_any(rule_id: str, entries: list[str]) -> bool:
    return any(_matches_rule_id(rule_id, entry) for entry in entries)


def _matches_rule_id(rule_id: str, entry: str) -> bool:
    """Exact id or family prefix (``L`` → ``L001``, ``SQL`` → ``SQL001``).

    A prefix matches when ``rule_id`` starts with ``entry`` and the remainder
    is all digits, so ``E`` matches ``E001`` but not ``ERR``, and ``S`` does
    not match ``S3G001`` (use ``S3G`` for that family).
    """
    if rule_id == entry:
        return True
    if not entry or not rule_id.startswith(entry):
        return False
    rest = rule_id[len(entry) :]
    return bool(rest) and rest.isdigit()


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


_STR_LIST_KEYS = (
    "allowed_domain_names",
    "forbidden_domain_names",
    "allowed_module_metadata",
    "forbidden_module_metadata",
    "forbidden_inline_ignore",
    "known_enum_bases",
    "nested_classes_whitelist",
    "known_first_party",
)

_INT_KEYS = (
    "min_name_length",
    "max_name_length",
    "max_noqa_comments",
    "exps_for_one_empty_line",
    "max_returns",
    "max_local_variables",
    "max_expressions",
    "max_arguments",
    "max_module_members",
    "max_methods",
    "max_line_complexity",
    "max_jones_score",
    "max_imports",
    "max_imported_names",
    "max_base_classes",
    "max_decorators",
    "max_string_usages",
    "max_awaits",
    "max_try_body_length",
    "max_module_expressions",
    "max_function_expressions",
    "max_asserts",
    "max_access_level",
    "max_attributes",
    "max_raises",
    "max_except_exceptions",
    "max_cognitive_score",
    "max_cognitive_average",
    "max_call_level",
    "max_annotation_complexity",
    "max_import_from_members",
    "max_tuple_unpack_length",
    "max_type_params",
    "max_match_subjects",
    "max_match_cases",
    "max_lines_in_finally",
    "max_conditions",
)


def _set_both(cfg: Config, m: dict[str, Any], snake: str, *, as_list: bool = False, as_int: bool = False) -> None:
    kebab = snake.replace("_", "-")
    if kebab in m:
        val = m[kebab]
    elif snake in m:
        val = m[snake]
    else:
        return
    if as_list:
        setattr(cfg, snake, list(val))
    elif as_int:
        setattr(cfg, snake, int(val))
    else:
        setattr(cfg, snake, val)


def _from_mapping(m: dict[str, Any]) -> Config:
    cfg = Config()
    if "select" in m:
        cfg.select = list(m["select"])
    if "ignore" in m:
        cfg.ignore = list(m["ignore"])
    if "exclude" in m:
        cfg.exclude = list(m["exclude"])
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
    for key in _STR_LIST_KEYS:
        _set_both(cfg, m, key, as_list=True)
    for key in _INT_KEYS:
        _set_both(cfg, m, key, as_int=True)
    _set_both(cfg, m, "cbp_import_prefix")
    return cfg


def _apply_overrides(cfg: Config, overrides: dict[str, Any]) -> Config:
    for key, value in overrides.items():
        if value is None:
            continue
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    return cfg
