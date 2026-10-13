"""Repairs for the second Codex results cli-16 to cli-21.

Acceptance:
- cli-16: `systemap figure --out figure.svg` replaces a link at the output path with a
  regular file. The target of the link keeps its text. A relative `--out` path whose
  folder is out of the repository gives exit 1, and the command writes no file.
- cli-17: `systemap serve` with an output directory that links out of the repository
  gives exit 1 with the path and the cause. The server does not start.
- cli-18: the router does not send a route through a region that is not the region of
  an endpoint, when a corridor exists. The test does not need a grid node in the region.
- cli-19: `systemap describe` and `systemap place --print` with a flow to an unknown
  component and a component without a position give exit 1 and the model finding.
  The output has no traceback.
- cli-20: the watched files of `systemap live` include each test file that extraction
  reads, also a file out of the source roots and the test directories. Python and
  TypeScript fixtures.
- cli-21: `systemap rules --json` without facts gives `"ok": false`, the missing facts in
  `problems`, and exit 1. Each `ok` value agrees with the exit code.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from conftest import write_tree
from test_import_rules import current
from test_place_route_repairs import _edit, _unplaced

from systemap import cli, live_watch
from systemap.cli import main
from systemap.route import route_all


def run(*argv: str) -> int:
    return main(list(argv))


# ---- cli-16: the figure output ------------------------------------------------------------


def test_figure_replaces_a_link_at_the_output_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    current(repo)
    outside = tmp_path / "outside.svg"
    outside.write_text("external", encoding="utf-8")
    link = repo / "docs/map/figure.svg"
    link.symlink_to(outside)
    capsys.readouterr()
    assert run("--root", str(repo), "figure", "--out", "figure.svg") == 0, capsys.readouterr()
    assert outside.read_text(encoding="utf-8") == "external"
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8").startswith("<svg")


def test_figure_replaces_a_link_at_an_absolute_output_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    current(repo)
    outside = tmp_path / "outside.svg"
    outside.write_text("external", encoding="utf-8")
    link = tmp_path / "figures/figure.svg"
    link.parent.mkdir()
    link.symlink_to(outside)
    capsys.readouterr()
    assert run("--root", str(repo), "figure", "--out", str(link)) == 0, capsys.readouterr()
    assert outside.read_text(encoding="utf-8") == "external"
    assert not link.is_symlink()


def test_figure_refuses_a_relative_output_out_of_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    current(repo)
    (tmp_path / "outside").mkdir()
    (repo / "docs/map/away").symlink_to(tmp_path / "outside", target_is_directory=True)
    capsys.readouterr()
    for out in ("away/figure.svg", "../../../outside/figure.svg"):
        assert run("--root", str(repo), "figure", "--out", out) == 1, out
        err = capsys.readouterr().err
        assert "the command does not use this file" in err, err
    assert list((tmp_path / "outside").iterdir()) == []


def test_figure_writes_a_relative_output_with_a_parent_part_in_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    assert run("--root", str(tmp_path), "figure", "--out", "../figure.svg") == 0
    assert (tmp_path / "docs/figure.svg").read_text(encoding="utf-8").startswith("<svg")


# ---- cli-17: the served directory --------------------------------------------------------


def test_serve_refuses_an_output_directory_out_of_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    current(repo)
    outside = tmp_path / "outside"
    write_tree(outside, {"index.html": "<html></html>", "secret.txt": "secret"})
    out = repo / "docs/map"
    shutil.rmtree(out)
    out.symlink_to(outside, target_is_directory=True)
    started: list[Path] = []

    def make_server(directory: Path, port: int) -> None:
        started.append(directory)
        raise AssertionError("the server started")

    monkeypatch.setattr(cli, "make_server", make_server)
    capsys.readouterr()
    assert run("--root", str(repo), "serve", "--port", "0") == 1
    assert started == []
    err = capsys.readouterr().err
    assert str(Path("docs/map")) in err and "is not in" in err, err


# ---- cli-18: the router and the regions ---------------------------------------------------


def _crosses(points: list[tuple[float, float]], box: tuple[float, float, float, float]) -> bool:
    bx, by, bw, bh = box
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if y0 == y1 and by < y0 < by + bh and min(x0, x1) < bx + bw and max(x0, x1) > bx:
            return True
        if x0 == x1 and bx < x0 < bx + bw and min(y0, y1) < by + bh and max(y0, y1) > by:
            return True
    return False


def test_a_route_avoids_an_unrelated_region_without_a_grid_node_in_it() -> None:
    cards = {"A": (20.0, 100.0, 150.0, 56.0), "B": (800.0, 100.0, 150.0, 56.0)}
    unrelated = (400.0, 90.0, 60.0, 100.0)
    regions = {"RA": (0.0, 80.0, 190.0, 100.0), "RB": (780.0, 80.0, 190.0, 100.0), "C": unrelated}
    routes = route_all(
        [("A", "B")], cards, set(), [], regions, {"A": "RA", "B": "RB"}, (1000.0, 300.0)
    )
    assert routes[0].fallback == ""
    assert not _crosses(routes[0].points, unrelated), routes[0].points


# ---- cli-19: endpoint findings before the placement --------------------------------------


UNKNOWN_FLOW = (
    'FLOWS = (Flow("Reader", "Writer", "request", "data"),)',
    'FLOWS = (Flow("Reader", "Writer", "request", "data"), '
    'Flow("Reader", "Missing", "record", "data"))',
    "flow Reader -> Missing has an unknown component",
)
UNKNOWN_KIND = (
    '        entry="read",\n',
    '        entry="read",\n        kind="widget",\n',
    "Reader has unknown kind widget",
)


@pytest.mark.parametrize("edit", [UNKNOWN_FLOW, UNKNOWN_KIND], ids=["flow", "kind"])
@pytest.mark.parametrize("command", [("describe",), ("place", "--print")])
def test_an_unknown_reference_gives_the_model_finding(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: tuple[str, ...],
    edit: tuple[str, str, str],
) -> None:
    path = _unplaced(tmp_path)
    old, new, finding = edit
    _edit(path, old, new)
    capsys.readouterr()
    assert run("--root", str(tmp_path), *command) == 1
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert finding in text, text
    assert "Traceback" not in text


# ---- cli-20: the watched test files ------------------------------------------------------


def _watched(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in live_watch.watched(root) if p.exists()}


def test_the_watcher_scans_python_test_pattern_files(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": (
                'language = "python"\ntests_dir = ["tests"]\ntest_patterns = ["qa/*.py"]\n'
                '[package_roots]\n"pkg" = "pkg"\n'
            ),
            "pkg/__init__.py": "",
            "tests/test_a.py": "def test_a() -> None:\n    pass\n",
            "qa/probe.py": "def test_probe() -> None:\n    pass\n",
            "other/probe.py": "",
        },
    )
    found = _watched(tmp_path)
    assert {"qa/probe.py", "tests/test_a.py"} <= found
    assert "other/probe.py" not in found


def test_the_watcher_scans_typescript_test_files_out_of_the_roots(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": (
                'language = "typescript"\ntest_patterns = ["qa/*.ts"]\n'
                '[package_roots]\n"src" = "app"\n'
            ),
            "src/app.ts": "export const app = 1;\n",
            "scripts/app.test.ts": "test('a', () => {});\n",
            "qa/probe.ts": "test('b', () => {});\n",
            "other/tool.ts": "export const tool = 1;\n",
        },
    )
    found = _watched(tmp_path)
    assert {"scripts/app.test.ts", "qa/probe.ts", "src/app.ts"} <= found
    assert "other/tool.ts" not in found


# ---- cli-21: the rules JSON result -------------------------------------------------------


def test_rules_json_without_facts_is_not_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    facts = tmp_path / "docs/map/map.json"
    facts.unlink()
    capsys.readouterr()
    code = run("--root", str(tmp_path), "rules", "--json")
    result = json.loads(capsys.readouterr().out)
    assert code == 1
    assert result["ok"] is False
    assert any(
        re.search(r"No facts are available at docs/map/map\.json", p) for p in result["problems"]
    )


def test_rules_json_ok_agrees_with_the_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    code = run("--root", str(tmp_path), "rules", "--json")
    result = json.loads(capsys.readouterr().out)
    assert (code == 0) == result["ok"] is True
