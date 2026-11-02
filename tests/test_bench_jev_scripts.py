"""The benchmark scripts in `bench/jev/` and `bench/typescript_adapter.py` (issue #109).

The scripts are not part of the package. These tests load them by path and operate
each changed function on the smallest input that the repository contains. They do not
call Jev, a coding agent, or the network.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
JEV = ROOT / "bench" / "jev"


@pytest.fixture
def jev_script(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import a script from `bench/jev/`, which imports its neighbours by name."""
    monkeypatch.syspath_prepend(str(JEV))
    for name in ("common", "score", "drift_labels", "moves", "relabel_time", "draft", "turns"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    def load(name: str) -> ModuleType:
        return importlib.import_module(name)

    return load


def test_score_package_helpers_use_the_package_facts(jev_script: Any) -> None:
    score = jev_script("score")
    records = {
        "app.web.views": {"package": "app.web"},
        "app.web.forms": {"package": "app.web"},
        "app.db.models": {"package": "app.db"},
    }
    owner = {"app.web.views": "Web", "app.web.forms": "Web", "app.db.models": "Store"}
    repo = SimpleNamespace(owner=owner, records=records)
    assert score.package_guess(repo, "app.web.views") == "Web"
    assert score.package_guess(repo, "app.db.models") is None


def test_score_pairs_baseline_uses_the_package_facts(
    jev_script: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    score = jev_script("score")
    records = {"a.x": {"package": "a"}, "a.y": {"package": "a"}, "b.z": {"package": "b"}}
    data = {
        "1": {"repo": "r", "id": "a.x|a.y", "label": {"tag": "same"}},
        "2": {"repo": "r", "id": "a.x|b.z", "label": {"tag": "easy"}},
    }
    res = {i: {"answers": {"same": {"noul": p}}} for i, p in (("1", 0.9), ("2", 0.1))}
    monkeypatch.setattr(score, "rows", lambda exp: data)
    monkeypatch.setattr(score, "results", lambda exp: res)
    monkeypatch.setattr(score, "usage_line", lambda res: "")
    monkeypatch.setattr(score, "load", lambda name: SimpleNamespace(records=records))
    score.score_pairs()
    assert "baseline same-package AUC      1.000" in capsys.readouterr().out


def test_drift_label_score_reads_the_committed_label_objects(
    jev_script: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    drift_labels = jev_script("drift_labels")
    drift_labels.score(str(JEV / "results" / "labels" / "agent-drift.json"))
    out = capsys.readouterr().out
    # results/labels/report.txt records these values for the same labels.
    assert "== test 7: 12 stale, 48 hold, 0 unsure" in out
    assert "AUC 0.957" in out


def test_label_files_accept_objects_and_flat_labels(jev_script: Any, tmp_path: Path) -> None:
    common = jev_script("common")
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"a": {"label": "successor", "reason": "r"}, "b": "unrelated"}))
    assert common.read_labels(path) == {"a": "successor", "b": "unrelated"}


def test_moves_label_score_counts_the_committed_successors(
    jev_script: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    moves = jev_script("moves")
    score = jev_script("score")
    monkeypatch.setattr(score, "rows", lambda exp: {})
    monkeypatch.setattr(score, "results", lambda exp: {})
    moves.score_labels(str(JEV / "results" / "labels" / "agent-moves.json"))
    # results/labels/report.txt records these counts for the same labels.
    assert "== test 8: 20 successors, 12 unrelated, 0 unsure" in capsys.readouterr().out


def test_relabel_time_renders_the_self_map(jev_script: Any) -> None:
    relabel_time = jev_script("relabel_time")
    html = relabel_time.render(ROOT, relabel_time.current_head())
    assert html.startswith("<!")


def test_draft_reads_the_facts_of_a_run(
    jev_script: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    draft = jev_script("draft")
    run = tmp_path / "self-first-map-1"
    run.mkdir()
    (run / "repo").symlink_to(ROOT, target_is_directory=True)
    top = draft.nest.load(draft.config.load(ROOT)).top
    monkeypatch.setattr(draft, "first_loadable", lambda run: (top.model, top.meaning, 0))
    found = draft.repos(run)
    assert found is not None
    final, _draft, edits = found
    assert final.name == "self" and edits == 0


def _load_by_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"bench_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_typescript_adapter_counts_the_exports(tmp_path: Path) -> None:
    adapter = _load_by_path(ROOT / "bench" / "typescript_adapter.py")
    (tmp_path / "a.ts").write_text(
        "export function f(): number { return 1 }\nexport const x = 2\n", encoding="utf-8"
    )
    assert adapter._export_counts(tmp_path) == (2, 2, 0)


def test_typescript_adapter_calls_only_present_functions() -> None:
    from systemap import extract, source_facts

    text = (ROOT / "bench" / "typescript_adapter.py").read_text(encoding="utf-8")
    for module, name in re.findall(r"\b(extract|source_facts)\.(\w+)\(", text):
        assert hasattr({"extract": extract, "source_facts": source_facts}[module], name)


def _history_row(name: str) -> list[str]:
    lines = (JEV / "README.md").read_text(encoding="utf-8").splitlines()
    head = lines.index("| repository | samples | cold | warm | windows that moved |")
    line = next(x for x in lines[head + 2 :] if x.startswith(f"| {name} | "))
    return [cell.strip() for cell in line.strip("|").split("|")]


@pytest.mark.parametrize("name", ["mealie", "rich"])
def test_history_table_agrees_with_the_result_file(name: str) -> None:
    found = json.loads((JEV / "results" / f"history-{name}.json").read_text(encoding="utf-8"))
    windows = found["windows"]
    keys = ("modules", "ways_in", "new_crossings", "gone_crossings", "grew")
    moved = sum(1 for w in windows if any(w[k] for k in keys))
    row = _history_row(name)
    assert row[1] == str(found["samples"])
    assert row[3] == f"{found['warm_seconds']}s"
    assert row[4] == f"{moved} of {len(windows)}"


def test_benchmark_lock_records_the_project_version() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((JEV / "uv.lock").read_text(encoding="utf-8"))
    locked = next(p for p in lock["package"] if p["name"] == "systemap")
    assert locked["version"] == project["project"]["version"]
