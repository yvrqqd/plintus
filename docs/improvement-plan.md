# plintus — ревью реализации и план улучшения v2

Это **вторая итерация** плана. Первая версия (`improvement-plan.md` до перезаписи)
была почти полностью выполнена: RAII `PyDocument`, валидация cache key с защитой
от path traversal, `rules_hash` с хешем исходника `check`, fallback worker'ов
на inline при non-builtin правилах, фикс DEC001 (сбор декораторов через
`decorated_definition`), типизированный `RuleContextConfig`, `Fix.safety`
валидация, table-driven тесты `string_utils`, CLI/worker/config тесты, CI на
3.10–3.13 + `cargo test --no-default-features` + clippy, бенчмарк с baseline
JSON. Ниже — только то, что **осталось** или **появилось** в процессе.

**Статус (2026-07-20):** Фаза 1 (п.п. 1–9) и Фаза 2 (п.п. 11–17, кроме
п.10) **выполнены**. Worker-тесты могут падать в macOS-sandbox
(`SC_SEM_NSEMS_MAX` / process spawn) — ограничение окружения, не баг кода.
П.10 (Rust `pair_role`) остаётся в Фазе 3 / perf backlog.

## Фаза 1 — Реальные баги (P0/P1) — DONE

1. **DONE** — `applied: bool` на `Diagnostic`; CLI text скрывает applied, JSON
   помечает; `apply_diagnostics_fixes` проставляет флаг.
2. **DONE** — общий `_diagnostic_sort_key` = `(path, start, rule_id, message)`.
3. **DONE** — corrupt cache → miss + rewrite (`JSONDecodeError`/`ValueError`).
4. **DONE** — `parser.error("--unsafe requires --fix or --diff")`.
5. **DONE** — мёртвая `_punctuation`-ветка убрана; фильтр `kind != "@"`.
6. **DONE** — `doc_id` удалён.
7. **DONE** — вводящий в заблуждение re-lint комментарий удалён (второй проход
   не реализован).
8. **DONE** — `can_safely_requote` отклоняет body, оканчивающееся на символ
   новой triple-кавычки; тесты в `test_string_utils.py`.
9. **DONE** — `dict_pair_role` останавливается на non-pair контейнерах; тесты
   nested в `test_phase4.py`.

## Фаза 2 — API / корректность (medium priority)

10. **OPEN** — `dict_pair_role` квадратичен (Rust `pair_role` на parse) — см. Фазу 3.

11. **DONE** — `_expr_name` unwrap `parenthesized_expression` + descend через
    `call`-receiver; `(eval)("x")` / `(foo()).bar()`; тесты в
    `test_resolve_call_name.py` + BAN001.

12. **DONE** — `Config.validate()` после TOML/CLI; type helpers отклоняют bare
    `str` списки и `"auto"` workers.

13. **DONE** — kebab+snake collision → `ValueError` через `_pick`.

14. **DONE** — `cli.py`: `d.severity == Severity.ERROR`.

15. **DONE** — `lint_file` → `(diags, source)`; `lint_paths` не читает файл
    повторно для `--fix`.

16. **DONE** — `apply_diagnostics_fixes` сортирует диагностики через
    `_diagnostic_sort_key` (вместо устаревшего «remaining»).

17. **DONE** — `Document.__del__` пишет ошибки `close()` в `sys.stderr`.

## Фаза 3 — Performance (Rust-ядро)

18. **`nodes_batch` строит `PyDict` на каждый node**
   - `crates/core/src/python.rs:103-129` — для `select(["string"])` с N строками
     это N PyDict'ей. Заменить на параллельные массивы (SOA): `ids: Vec<u32>`,
     `kinds: Vec<&str>`, `starts: Vec<usize>`, …, и собирать `Node` в Python из
     кортежей по индексу. Измерить в `run_bench.py` на 50-файловом корпусе.

19. **`Node` dataclass frozen=True + `_text` — лишнее копирование**
   - `document.py:14-24` — `frozen=True` dataclass создаёт `__hash__` и
     `__setattr__`-блок. Для горячего пути (N nodes) это лишние накладные.
     Заменить на `__slots__`-класс без frozen (rules не мутируют Node).

20. **`kind_index: HashMap<&'static str, Vec<u32>>` → `Vec<u32>` по kind-id**
   - `document.rs:31` — заменить `&'static str` ключ на interned `u16` kind-id
     со статической таблицей `KIND_NAMES: &[&str]`. `select` становится O(1)
     lookup по `Vec<u32>` без хеширования строки. Совместимо с п.10 (pair-role).

21. **`parse_source` клонирует source в `Document.source: String`**
   - `parse.rs:106` — Python уже держит `str`, Rust клонирует в `String`. Для
     больших файлов это двойная память. Использовать `Arc<str>` (Python передаёт
     `&str`, Rust хранит `Arc<str>`, Python-wrapper хранит тот же `Arc` через
     PyO3 borrowing). Убрать тройное хранение source.

22. **`build_line_starts` уже на `memchr`** — OK, ничего не делать.

23. **`walk_iter` уже итеративный** — OK. Замерить, нужен ли `smallvec` для
    `Frame`-стека на типичных файлах (<5 уровней вложенности).

## Фаза 4 — Тесты (дополнить)

24. **Тест на повреждённый cache-файл** (после п.3): записать мусор, проверить
    cache-miss fallback.

25. **Тест на `--fix` + `--output-format json`** (после п.1): проверить, что
    применённые fix'ы не появляются в JSON-выводе (или помечены `applied: true`).

26. **Тест на `--unsafe` без `--fix`** (после п.4): ожидать exit 2 (argparse error)
    или warning в stderr.

27. **Тест на несогласованную сортировку** (после п.2): два правила на одном
    span'е с разными сообщениями — сравнить порядок `lint_source` vs `lint_paths`.

28. **Тест на `_expr_name` edge-cases** (после п.11): `(foo()).bar` и `(eval)("x")`
    — документировать текущее поведение или фикс.

29. **Тест на `apply_diagnostics_fixes` с `remaining`** (после п.16): проверить
    что `remaining` отсортирован.

30. **Тест на `Config` validation** (после п.12, п.13): `workers = "auto"`,
    `select = "Q001"` (строка), `dict-quotes = "weird"` через `_from_mapping`,
    `--workers -1` через `_apply_overrides` → `ValueError`. Kebab+snake collision
    → `ValueError` или warning.

31. **Тест на re-lint после fix** (после п.7): если реализован второй проход —
    проверить, что фиксы не генерируют новых диагностик.

32. **Тест на `requote` triple-quote edge cases** (после п.8): body, оканчивающееся
    на `'` или `"`, для triple→triple переключения → `requote` возвращает `None`.
    Round-trip: `requote` результат должен `compile()` без `SyntaxError`.

33. **Тест на `dict_pair_role` nested containers** (после п.9): tuple/list/subscript/
    call внутри dict value не флагаются Q001; вложенный dict остаётся флагаемым.

34. **Worker-тест пометить sandbox-skip** — `test_lint_paths_parallel_matches_inline`
    падает в macOS-sandbox. Добавить `pytest.mark.skipif` по `os.environ` или
    `sys.platform` + проверке `SC_SEM_NSEMS_MAX`, чтобы тест не падал в CI-sandbox.

35. **Snapshot включает `fix.replacement`** — уже включён (`quotes_and_banned.snapshot.json`).
    OK.

## Фаза 5 — Документация

36. **README example актуален** — уже использует `requote`/`Fix.replace`. OK.

37. **`docs/configuration.md`** — все ключи задокументированы, включая
    `worker-threshold`. OK. Добавить пример `--unsafe` semantics и поведение
    `--fix` + `--output-format json` после п.1. Документировать kebab-vs-snake
    precedence (после п.13).

38. **`docs/cli.md`** — добавить `--unsafe` без `--fix` поведение (после п.4).

39. **`docs/plugin-authoring.md`** — добавить секцию про `pair_role` helper
    (после п.10, если появляется в API) и edge-cases `_expr_name` (после п.11).

40. **`docs/architecture.md`** — обновить секцию "Performance principles" с
    актуальными замерами из `run_bench.py --baseline`.

41. **`docs/rules-catalog.md`** — чёткая маркировка shipped vs planned уже есть
    ("What's shipped today"). OK.

## Фаза 6 — Упаковка / CI / бенчмарки

42. **CI уже покрывает** 3.12–3.14, `cargo test --no-default-features`, clippy,
    ruff, mypy (non-blocking). OK. Расширение matrix при необходимости.

43. **`mypy src || true`** — сделать блокирующим после того, как аннотации
    полные. Сейчас `RuleContext.config` — `RuleContextConfig | dict[str, Any]`,
    что не полностью типизировано в правилах. После п.10 убрать `dict[str, Any]`
    из union.

44. **`benchmarks/run_bench.py`** — добавить замер `nodes_batch` overhead
    (после п.18) до и после SOA-оптимизации. Сохранить baseline в
    `benchmarks/baseline.json` (gitignored или committed — решить).

45. **`.gitignore`** — уже содержит `plintus_bench_*/`. OK.

## Порядок выполнения

Фаза 1 (баги) → Фаза 4 (тесты на регрессию параллельно) → Фаза 2 (API) →
Фаза 3 (perf, с замерами до/после) → Фаза 5/6 (доки/CI). Каждый пункт —
отдельный коммит/PR. Фаза 3 — только после того, как `run_bench.py --baseline`
зафиксирован, чтобы был regression-detection.
