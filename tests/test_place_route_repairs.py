"""Repairs for the Codex results cli-4, cli-5, cli-6, cli-7, cli-8, and cli-12.

Acceptance:
- cli-4: `systemap place` writes positions into a Component with positional x and y values.
  If the command cannot load the changed model file, the file has its previous bytes.
  The command exits 1 with an error that names the model file.
- cli-5: `systemap refresh` exits 1 for an import rule with the result fail, as
  `systemap check` does. A second refresh without file changes also exits 1.
  The output gives the import.
- cli-6: `place.compute` gives a layout for regions in the container sequence C1, C2, C1.
- cli-7: `systemap place` writes a positional canvas. If the loaded geometry is not the
  calculated geometry, the command exits 1, the file has its previous bytes, and the
  error names the value that the command could not write.
- cli-8: a new container card does not touch a region box or a region header.
- cli-12: the model check refuses a flow with the same component at the two ends.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, sample_model, write_tree
from test_import_rules import FORBID, _with_rules, current

from systemap import config, model_load, place
from systemap.cli import main
from systemap.model import Component, Container, Flow, Model, Region, problems
from systemap.schematic import geometry


def run(*argv: str) -> int:
    return main(list(argv))


def _unplaced(root: Path) -> Path:
    """Write the two-card map without positions. Give the model path."""
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    path = root / "map/model.py"
    text = re.sub(r"^\s+[xy]=\d+,\n", "", path.read_text(encoding="utf-8"), flags=re.M)
    path.write_text(text, encoding="utf-8")
    return path


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def _geometry(model: Model) -> tuple[object, ...]:
    return (
        model.canvas,
        tuple((c.id, c.x, c.y) for c in model.components),
        tuple((r.id, r.box) for r in model.regions),
        tuple((b.id, b.box) for b in model.containers),
    )


READER_KEYWORDS = (
    "    Component(\n"
    '        id="Reader",\n'
    '        region="core",\n'
    '        does="Reads the input and turns it into a request.",\n'
    '        interface="read(source) -> Request",\n'
    '        implemented_by=("pkg.reader",),\n'
    '        entry="read",\n'
    "    ),\n"
)
READER_POSITIONAL = (
    '    Component("Reader", "Reads the input and turns it into a request.", '
    '"read(source) -> Request", ("pkg.reader",), "read", "component", "core", None, '
    "None, None),\n"
)


# ---- cli-4 ---------------------------------------------------------------------------


def test_place_writes_positional_coordinates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _unplaced(tmp_path)
    _edit(path, READER_KEYWORDS, READER_POSITIONAL)
    before, _meaning = config.load_model(path)
    assert run("--root", str(tmp_path), "place") == 0, capsys.readouterr()
    after, _meaning = config.load_model(path)
    assert _geometry(after) == _geometry(place.apply(before, place.compute(before)))
    assert re.search(r'"core", None, \d+, \d+\),', path.read_text(encoding="utf-8"))


def test_place_restores_the_model_file_when_the_reload_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _unplaced(tmp_path)
    # The command writes LF line ends. On Windows the helper writes CRLF, so the file is
    # made LF first. Otherwise the written file is smaller and the reader accepts it.
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    # The model file is a few bytes below the limit of the model reader. Thus the reader
    # refuses the file after the command adds the x and y values.
    size = len(path.read_bytes())
    pad = model_load.MAX_BYTES - size - 4
    path.write_bytes(path.read_bytes() + b"#" * (pad - 1) + b"\n")
    before = path.read_bytes()
    config.load_model(path)
    capsys.readouterr()
    assert run("--root", str(tmp_path), "place") == 1
    err = capsys.readouterr().err
    assert path.read_bytes() == before
    assert "map/model.py" in err and "restored" in err, err
    assert "more than 524288 bytes" in err, err


# ---- cli-5 ---------------------------------------------------------------------------


def test_refresh_exits_1_for_a_failed_import_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    _with_rules(tmp_path, FORBID)
    # A source change makes the facts stale, so the first refresh writes its outputs.
    reader = tmp_path / "pkg/reader.py"
    reader.write_text(reader.read_text(encoding="utf-8") + "\n\nLIMIT = 1\n", encoding="utf-8")
    capsys.readouterr()
    assert run("--root", str(tmp_path), "check") == 1
    capsys.readouterr()
    assert run("--root", str(tmp_path), "refresh") == 1
    out = capsys.readouterr().out
    assert "  writer-alone (forbid_import): pkg.writer imports pkg.reader" in out
    assert "map: The command updated" in out
    # The second refresh has no file to write. It also examines the rules.
    assert run("--root", str(tmp_path), "refresh", "--quiet") == 1
    out = capsys.readouterr().out
    assert "  writer-alone (forbid_import): pkg.writer imports pkg.reader" in out
    assert "map: The command updated" not in out


# ---- cli-6 ---------------------------------------------------------------------------


def test_place_accepts_regions_that_alternate_between_containers() -> None:
    model = Model(
        canvas=(100, 100),
        containers=(
            Container("c1", "ONE", (0, 0, 1, 1)),
            Container("c2", "TWO", (0, 0, 1, 1)),
        ),
        regions=(
            Region("r1", "R1", (0, 0, 1, 1), container="c1"),
            Region("r2", "R2", (0, 0, 1, 1), container="c2"),
            Region("r3", "R3", (0, 0, 1, 1), container="c1"),
        ),
        components=(
            Component("A", "a", region="r1"),
            Component("B", "b", region="r2"),
            Component("C", "c", region="r3"),
        ),
        flows=(Flow("A", "B", "x", "data"), Flow("B", "C", "y", "data")),
        flow_kinds=(),
    )
    placement = place.compute(model)
    assert sorted(placement.order) == ["r1", "r2", "r3"]
    assert place.apply(model, placement).layout_problems() == []


# ---- cli-7 ---------------------------------------------------------------------------


def test_place_writes_a_positional_canvas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _unplaced(tmp_path)
    _edit(path, "MODEL = Model(\n    canvas=(600, 300),\n", "MODEL = Model(\n    (600, 300),\n")
    before, _meaning = config.load_model(path)
    assert run("--root", str(tmp_path), "place") == 0, capsys.readouterr()
    after, _meaning = config.load_model(path)
    assert _geometry(after) == _geometry(place.apply(before, place.compute(before)))


def test_place_refuses_a_box_that_the_edit_cannot_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _unplaced(tmp_path)
    write_tree(
        tmp_path,
        {
            "map/layout.py": (
                "from systemap import Region\n\n"
                'REGIONS = (Region(id="core", label="CORE", box=(40, 60, 100, 100), '
                'container="system"),)\n'
            )
        },
    )
    _edit(
        path,
        'REGIONS = (Region(id="core", label="CORE", box=(40, 60, 520, 200), container="system"),)\n',
        "import layout\n\nREGIONS = layout.REGIONS\n",
    )
    before = path.read_bytes()
    capsys.readouterr()
    assert run("--root", str(tmp_path), "place") == 1
    err = capsys.readouterr().err
    assert path.read_bytes() == before
    assert "region core" in err and "restored" in err, err


# ---- cli-8 ---------------------------------------------------------------------------


def test_a_new_container_card_does_not_touch_a_region() -> None:
    model = Model(
        canvas=(816, 466),
        containers=(Container("c", "SYSTEM", (0, 0, 800, 450)),),
        regions=(Region("r", "WORK", (20, 60, 390, 300), container="c"),),
        components=(
            Component("Kept", "k", region="r", x=40, y=200),
            Component("User", "u", kind="actor", container="c"),
        ),
        flows=(),
        flow_kinds=(),
    )
    placement = place.compute(model)
    placed = place.apply(model, placement)
    user = placed.component("User").box
    region = placed.regions[0].box
    headers = [h["box"] for h in geometry(placed).headers if h["kind"] == "region"]

    def touches(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
        return (
            a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
        )

    assert not touches(user, region), user
    assert not any(touches(user, tuple(h)) for h in headers), user
    assert placed.layout_problems() == []


# ---- cli-12 --------------------------------------------------------------------------


def test_the_model_check_refuses_a_flow_to_the_same_component() -> None:
    model, meaning = sample_model()
    a = model.components[0].id
    looped = dataclasses.replace(model, flows=(*model.flows, Flow(a, a, "record", "data")))
    found = [p for p in problems(looped, meaning) if p.startswith(f"placement: flow {a} -> {a}")]
    assert found == [
        f"placement: flow {a} -> {a} has the same component at the two ends. "
        "A flow must connect two different components"
    ]
