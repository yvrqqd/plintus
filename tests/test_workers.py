from __future__ import annotations

from pathlib import Path

from plintus.config import Config
from plintus.engine import lint_paths
from plintus.workers import decide_workers


def test_decide_workers_threshold():
    cfg = Config(workers=0, worker_threshold=10)
    assert decide_workers(5, cfg) == 1
    assert decide_workers(50, cfg) > 1
    cfg2 = Config(workers=1, worker_threshold=1)
    assert decide_workers(100, cfg2) == 1


def test_lint_paths_smoke(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("eval('1')\n", encoding="utf-8")
    cfg = Config(cache=False, workers=1, select=["BAN001"], worker_threshold=9999)
    diags, _ = lint_paths([str(tmp_path)], cfg)
    assert any(d.rule_id == "BAN001" for d in diags)


def test_lint_paths_multi_workers(tmp_path: Path):
    """Integration: workers>1 must still surface diagnostics."""
    for i in range(8):
        (tmp_path / f"f{i}.py").write_text("eval('1')\n", encoding="utf-8")
    cfg = Config(cache=False, workers=2, select=["BAN001"], worker_threshold=1)
    assert decide_workers(8, cfg) > 1
    diags, _ = lint_paths([str(tmp_path)], cfg)
    assert len([d for d in diags if d.rule_id == "BAN001"]) == 8
