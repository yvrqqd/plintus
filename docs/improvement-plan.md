# plintus — ревью реализации и план улучшения v2

Это **вторая итерация** плана. Первая версия (`improvement-plan.md` до перезаписи)
была почти полностью выполнена: RAII `PyDocument`, валидация cache key с защитой
от path traversal, `rules_hash` с хешем исходника `check`, fallback worker'ов
на inline при non-builtin правилах, фикс DEC001 (сбор декораторов через
`decorated_definition`), типизированный `RuleContextConfig`, `Fix.safety`
валидация, table-driven тесты `string_utils`, CLI/worker/config тесты, CI на
3.10–3.13 + `cargo test --no-default-features` + clippy, бенчмарк с baseline
JSON. Ниже — только то, что **осталось** или **появилось** в процессе.

Текущее состояние: 65/66 тестов проходят (1 failure —
`test_lint_paths_parallel_matches_inline` — падает из-за sandbox-блока
`os.sysconf("SC_SEM_NSEMS_MAX")` на macOS, не баг кода; вне sandbox проходит).

**Вторая итерация (v2.1):** добавлены 5 багов, найденных субагентом-багхантером
(п.п. 8, 9, 11, 12, 13). Из них 2 критических (P0/P1 — повреждают код
пользователя через `--fix`): `requote` генерирует SyntaxError для triple-quoted
strings (п.8) и `dict_pair_role` ошибочно флагает вложенные строки (п.9).

## Фаза 1 — Реальные баги (P0/P1)

1. **`apply_diagnostics_fixes` теряет fixed-диагностики молча**
   - Файл: `src/plintus/engine.py:310-342`, `lint_paths:237-241`
   - `lint_paths` вызывает `apply_diagnostics_fixes`, получает `remaining`, но
     `remaining` нигде не используется и не возвращается. `--fix --output-format
     json` печатает **все** диагностики, включая уже применённые — вводит в
     заблуждение (CI думает, что фикс не сработал).
   - Решение: возвращать `remaining` из `lint_paths` либо помечать применённые
     диагностики флагом `applied: bool` в `Diagnostic`. CLI `--fix` должен
     печатать только `remaining` (или помечать `applied`).

2. **Несогласованная сортировка диагностики**
   - `lint_source` (`engine.py:157`): сортирует по `(path, start, rule_id, message)`.
   - `lint_paths` (`engine.py:243`): сортирует по `(path, start, rule_id)` — без `message`.
   - При двух диагностиках одного правила на одном span'е с разными сообщениями
     порядок между `lint_source` и `lint_paths` различается. Унифицировать ключ.

3. **Cache hit на повреждённом файле роняет процесс**
   - Файл: `engine.py:140-142`
   - `json.loads(cached)` на повреждённом кэше бросает `json.JSONDecodeError`,
     которое поднимается как opaque-исключение вместо cache-miss.
   - Обернуть в `try/except (json.JSONDecodeError, ValueError)` → treat as miss +
     удалить/перезаписать битый файл. Тест: записать мусор в cache-файл, проверить
     что lint проходит мимо кэша.

4. **`--unsafe` без `--fix` молча ничего не делает**
   - Файл: `cli.py:26, 70`
   - `--unsafe` влияет только на `apply_diagnostics_fixes`, но если `--fix`/`--diff`
     не передан — `apply_fixes=False`, флаг проигнорирован.
   - Либо `parser.error("--unsafe requires --fix or --diff")`, либо warn в stderr.

5. **`require_decorator.py:67` — мёртвая проверка `endswith("_punctuation")`**
   - `child.kind.endswith("_punctuation")` никогда не истинно для tree-sitter-python
     (там kinds вроде `"@"`, `"("`, не `"at_punctuation"`). Реально работает только
     `child.kind not in ("@",)`. Убрать мёртвую ветку, оставить явный фильтр по
     `child.is_named` (доступно через `nodes_batch["named"]`).

6. **`document.py:50-53` — `doc_id` property мёртвый**
   - Возвращает `id(self._py)`, ничего в коде его не использует. Удалить.

7. **`engine.py:240` — вводящий в заблуждение комментарий**
   - `# re-lint after fix for remaining issues (idempotent second pass optional)`
     — ре-линта нет. Удалить комментарий либо реализовать второй проход
     (рекомендуется: второй проход только если `remaining` непуст после fix).

8. **`requote` генерирует SyntaxError для triple-quoted strings (P0)**
   - Файл: `src/plintus/rules/string_utils.py:33-42, 74-93`
   - `can_safely_requote` для triple-кавычек проверяет только отсутствие `'''`/`"""`
     в теле, но не проверяет, что тело **заканчивается** символом новой кавычки.
     `requote('"""it\'"""', "single")` → `("'''it''''", True)`, что парсится как
     `'''it'''` + unterminated `'` → SyntaxError. Фикс помечен `safe=True`, поэтому
     `--fix` применит его автоматически и **сломает код пользователя**.
   - Решение: в `can_safely_requote` для triple `new_quote` также отклонять тела,
     заканчивающиеся символом новой кавычки (`body.endswith(new_quote[0])`), либо
     проверять, что `body + new_quote` не содержит 4+ подряд одинаковых кавычек.
   - Тест: `requote('"""it\'"""', "single") is None`; зеркальный случай для `"`;
     table-driven в `test_string_utils.py` с телами, оканчивающимися на `'`/`"`.

9. **`dict_pair_role` ошибочно классифицирует вложенные строки как "dict value" (P1)**
   - Файл: `src/plintus/api.py:177-204`
   - При walk'е к ближайшему `pair` правило возвращает `"value"` для **любой** строки
     в поддереве значения, игнорируя промежуточный контейнер. Q001 флагает элементы
     tuple/list, индексы subscript, аргументы call внутри dict value — и применяет
     к ним safe-fix. `d = {"k": ("a", "b")}` даёт 3 диагностики вместо 1, `--fix`
     переписывает tuple-элементы.
   - Решение: в ancestor-walk branch возвращать `"value"` только если string (или
     её непосредственный parent) **является** value-node пары. Останавливать walk на
     первом не-pair контейнере (`list`/`tuple`/`subscript`/`call`/`argument_list`)
     и возвращать `None`.
   - Тест: `d = {"k": ("a", "b")}` → 1 Q001 (только key); `d = {"k": v["x"]}` → 1
     (только key); `d = {"k": foo("x")}` → 1; `d = {"k": {"nested": "v"}}` → 3
     (вложенный dict должен остаться флагаемым).

## Фаза 2 — API / корректность (medium priority)

10. **`dict_pair_role` квадратичен**
   - Файл: `api.py:177-204`
   - На каждый строковый node зовёт `ancestors` + `children(parent)`. Для файла с
     N строками в dict'ах это O(N × depth). Кешировать pair-role на этапе parse
     (Rust пробегает CST один раз — может разметить `string` как `key`/`value`
     сразу и класть в `NodeData` поле `pair_role: Option<u8>`).

11. **`_expr_name` для attribute и parenthesized receivers**
   - Файл: `api.py:244-266`
   - Для `(foo()).bar` — `objs[0]` это `call`, не `identifier`/`attribute`, цикл
     `break`-ает и теряет `bar`. Для `(eval)("x")` — `parenthesized_expression`
     не обрабатывается, `resolve_call_name` возвращает `None`, BAN001 молча
     пропускает забаненный вызов (false negative на реальном способе вызова).
     Документировать либо обработать (вызовы-ресиверы встречаются в реальном коде:
     `df.groupby('x').sum()`; `(eval)()` — обходная паттерн для обфускации).
   - Решение: в `_expr_name` добавить case для `parenthesized_expression`
     (рекурсивно в единственного child) и для `call`-receiver (взять function
     call'а как receiver для attribute).

12. **`Config` не валидирует типы полей из TOML и CLI**
   - Файл: `config.py:149-205`
   - `Config.__post_init__` валидирует `dict_quotes`/`message_quotes`/`workers`/
     `worker_threshold`, но `_from_mapping` и `_apply_overrides` мутируют поля
     через `setattr` **без повторной валидации** — `__post_init__` не вызывается.
     `dict-quotes = "weird"` в pyproject.toml принимается молча → Q001/Q002
     флагают все строки, `desired_quote_char` падает в else-ветку и возвращает
     `"""`. `--workers -1` из CLI тоже молча принимается.
   - Дополнительно: `int(m["workers"])` падает с `TypeError` на `workers = "auto"`.
     `select = "Q001"` (строка вместо списка) тихо станет итерируемой —
     `enabled("Q")` вернёт True по in-проверке.
   - Решение: вынести валидацию в `validate()` метод, звать из `__post_init__` и
     из конца `_from_mapping`/`_apply_overrides`. Добавить `_typecheck` хелпер
     с человекочитаемыми ошибками для всех ключей (включая `select`/`ignore`/
     `banned_calls`/etc. как списки строк).
   - Тест: `_from_mapping({"dict-quotes": "weird"})` → `ValueError`;
     `_from_mapping({"workers": "auto"})` → `ValueError`; `_from_mapping({"select": "Q001"})`
     (строка) → `ValueError`; `_apply_overrides(cfg, {"workers": -1})` → `ValueError`.

13. **`_from_mapping` молча даёт snake_case перекрыть kebab-case**
   - Файл: `config.py:149-196`
   - Для всех ключей с обоими вариантами (`cache-dir`/`cache_dir`, `dict-quotes`/
     `dict_quotes`, и т.д.) snake-branch обрабатывается **после** kebab-branch,
     поэтому при случайном наличии обоих — snake выигрывает молча. Footgun:
     `cache-dir = "a"` + `cache_dir = "b"` → `b` без предупреждения.
   - Решение: для каждого ключа с обоими формами detect presence обоих и raise
     (или warn); либо документировать явное правило precedence.

14. **`cli.py:92` — строковое сравнение severity**
   - `d.severity.value == "error"` → `d.severity == Severity.ERROR`. Чисто.

15. **`lint_paths` повторно читает файл для fix**
   - `engine.py:234-236` — `lint_file` уже прочитал source, но `lint_paths`
     открывает файл снова. `lint_file`/`lint_source` могут возвращать source
     вместе с диагностиками (или `lint_paths` зовёт `lint_source` напрямую).

16. **`apply_diagnostics_fixes` возвращает `remaining` неотсортированным**
   - Порядок зависит от того, какие fix'ы оказались overlapping. Сортировать
     `remaining` по `(start, rule_id)` перед возвратом.

17. **`Document.__del__` глотает все исключения**
   - `document.py:69-73` — `except Exception: pass`. Хотя `close()` идемпотентен,
     скрытые ошибки затрудняют отладку. Логировать в stderr через
     `sys.stderr.write(...)` (не `print`, чтобы не ломать capture в тестах без
     capsys).

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
