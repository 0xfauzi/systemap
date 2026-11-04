"""A tree of maps on three levels, and the commands that examine one map with `--map`.

Acceptance values:

1. The fixture of `three_levels` has 11 maps and nested maps on level 1, 2, and 3. A map
   on level 2 imports a module of the top card Base, and it has the actor Base. After
   `place`, `extract`, and `refresh`, `check` exits 0, and `judgement` exits 0.
2. `nest.load(cfg, only=ID)` loads the ancestors of the map, the map, and its
   descendants, and no other map. `.` selects the top map. An unknown map ID gives an
   option error. A load without `only` gives the full tree, as before.
3. With a syntax error in the model file of a sibling map, each command with `--map`
   gives the same exit code as before the error. These commands are `check`,
   `judgement`, `rules`, `place`, `describe`, `journeys`, `review`, `decisions pending`,
   and `decisions status`. The full `check` stops with exit code 2.
4. A run with `--map` reports only the lines of that map. `judgement --map` gives no
   entry point lines and says that it did not examine the entry coverage. An answer for a
   line of a different map is not stale in a run with `--map`.
5. `decisions pending --map ID` gives the requests of that map with the same request IDs
   as the full-tree snapshot that `decisions submit` uses.
6. `place --map ID` writes only the model file of that map.
7. `refresh`, `extract`, and `decisions submit` refuse `--map` with exit code 2.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
import three_levels
from conftest import write_tree

from systemap import cli_scope, config, decisions_submit, nest
from systemap.cli import main

ALL = three_levels.map_ids()
CHOSEN = "P0/Q0"
SIBLING = "P1"


def run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("three_levels")
    write_tree(root, three_levels.files())
    assert run(root, "place") == 0
    assert run(root, "extract") == 0
    assert run(root, "refresh", "--quiet") == 0
    return root


@pytest.fixture
def tree_root(built: Path, tmp_path: Path) -> Path:
    root = tmp_path / "copy"
    shutil.copytree(built, root)
    return root


def _break(root: Path, map_id: str) -> None:
    path = root / "map" / three_levels.parts_mod.file_name(map_id)
    path.write_text(path.read_text(encoding="utf-8") + "\nCOMPONENTS = (\n", encoding="utf-8")


def test_the_fixture_has_eleven_maps_on_three_levels(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1."""
    tree = nest.load(config.load(tree_root))
    assert tree.ids == ALL
    assert len(tree.maps) == three_levels.map_count() == 11
    assert max(m.id.count("/") + 1 for m in tree.maps if m.id) == 3
    level_2 = tree.get(CHOSEN)
    assert "Base" in level_2.model.ids
    assert tree.get("P0").model.component("Base").kind == "actor"
    facts = json.loads((tree_root / "docs/map/map.json").read_text(encoding="utf-8"))
    assert "pkg.base.util" in facts["components"]["pkg.p0.q0.r0"]["uses"]
    capsys.readouterr()
    assert run(tree_root, "check") == 0
    assert run(tree_root, "judgement") == 0


def test_the_scoped_load_reads_the_chain_and_the_descendants(tree_root: Path) -> None:
    """Acceptance 2."""
    cfg = config.load(tree_root)
    tree = nest.load(cfg, CHOSEN)
    assert tree.ids == ["", "P0", "P0/Q0", "P0/Q0/Deep"]
    assert tree.partial and tree.selected == CHOSEN
    assert [m.id for m in tree.reported] == [CHOSEN]
    top = nest.load(cfg, nest.TOP_ID)
    assert top.selected == "" and [m.id for m in top.reported] == [""]
    full = nest.load(cfg)
    assert not full.partial and full.reported == full.maps and full.ids == ALL
    with pytest.raises(config.ArgumentError, match="unknown map id: P0/Nope"):
        nest.load(cfg, "P0/Nope")
    with pytest.raises(config.ArgumentError, match="Base is not a component that opens a map"):
        nest.load(cfg, "Base")


SCOPED = [
    ("check", "--map", CHOSEN),
    ("judgement", "--map", CHOSEN),
    ("rules", "--map", CHOSEN),
    ("describe", "--map", CHOSEN),
    ("journeys", "--dry-run", "--map", CHOSEN),
    ("review", "R0", "--dry-run", "--map", CHOSEN),
    ("decisions", "pending", "--map", CHOSEN),
    ("decisions", "status", "--map", CHOSEN),
    ("place", "--map", CHOSEN),
]


@pytest.mark.parametrize("argv", SCOPED, ids=[" ".join(a[:2]) for a in SCOPED])
def test_a_broken_sibling_does_not_change_a_scoped_command(
    tree_root: Path, argv: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3."""
    before = run(tree_root, *argv)
    _break(tree_root, SIBLING)
    _break(tree_root, "P0/Q1")
    capsys.readouterr()
    assert run(tree_root, *argv) == before
    assert "map/p1.py" not in capsys.readouterr().err
    assert run(tree_root, "check") == 2


def test_a_scoped_judgement_reports_only_its_map(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4."""
    module = tree_root / "pkg/p0/q0/r0.py"
    route = 'from fastapi import FastAPI\napp = FastAPI()\n\n\n@app.get("/read")\ndef run_0_0'
    module.write_text(module.read_text(encoding="utf-8").replace("def run_0_0", route))
    assert run(tree_root, "extract") == 0
    capsys.readouterr()
    assert run(tree_root, "judgement", "--json") == 0
    full = [row["line"] for row in json.loads(capsys.readouterr().out)["open"]]
    other = next(line for line in full if line.startswith("P1: "))
    assert any(line.startswith(f"{CHOSEN}: entry point ") for line in full)
    toml = tree_root / "systemap.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8")
        + f'\n[[judgement.answered]]\nitem = {json.dumps(other)}\nreason = "A test."\n',
        encoding="utf-8",
    )
    assert run(tree_root, "judgement", "--json", "--map", CHOSEN) == 0
    captured = capsys.readouterr()
    scoped = json.loads(captured.out)
    lines = [row["line"] for row in scoped["open"]]
    assert lines and all(line.startswith(f"{CHOSEN}: ") for line in lines)
    assert scoped["stale_answers"] == []
    assert scoped["scope"] == {"map": CHOSEN, "entry_coverage": "not examined"}
    assert "entry coverage: not examined in a run with --map" in captured.err
    assert run(tree_root, "judgement", "--map", CHOSEN) == 0
    text = capsys.readouterr().out
    assert other not in text and "entry point" not in text
    # Without the scope, the answer of the line of P1 is stale in the scoped run.
    tree = nest.load(config.load(tree_root), CHOSEN)
    assert not cli_scope.in_scope(tree, other) and cli_scope.in_scope(tree, lines[0])


def test_scoped_requests_have_the_ids_of_the_full_tree(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 5."""
    full = decisions_submit.snapshot(config.load(tree_root))
    wanted = sorted(rid for rid, r in full.requests.items() if r.map == CHOSEN)
    capsys.readouterr()
    assert run(tree_root, "decisions", "pending", "--json", "--map", CHOSEN) == 0
    rows = json.loads(capsys.readouterr().out)["requests"]
    assert wanted and sorted(row["id"] for row in rows) == wanted


def test_a_scoped_place_writes_only_its_model_file(tree_root: Path) -> None:
    """Acceptance 6."""
    files = sorted((tree_root / "map").glob("*.py"))
    for path in files:
        text = re.sub(r", x=\d+, y=\d+\)", ")", path.read_text(encoding="utf-8"))
        path.write_text(text, encoding="utf-8")
    before = {path: path.read_bytes() for path in files}
    chosen = tree_root / "map" / three_levels.parts_mod.file_name(CHOSEN)
    assert run(tree_root, "place", "--map", CHOSEN) == 0
    assert [path for path in files if path.read_bytes() != before[path]] == [chosen]


@pytest.mark.parametrize(
    "argv",
    [("refresh",), ("extract",), ("decisions", "submit", "-")],
    ids=["refresh", "extract", "decisions submit"],
)
def test_commands_for_all_maps_refuse_the_map_option(
    tree_root: Path, argv: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 7."""
    with pytest.raises(SystemExit) as stopped:
        run(tree_root, *argv, "--map", CHOSEN)
    assert stopped.value.code == 2
    assert "writes the shared files of all maps" in capsys.readouterr().err
