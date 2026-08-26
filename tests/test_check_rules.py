"""The entry and stale rules of `systemap check`, and the bare figure.

Every case starts from what `systemap init` writes and refreshes once, so
the map is current, and then breaks exactly one thing.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import TWO_CARD_MODEL, Sample, init_two_cards, write_tree

from systemap import check, route
from systemap.cli import main
from systemap.model import Container, all_layers
from systemap.schematic import render as render_schematic

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def current(root: Path) -> None:
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    assert run("--root", str(root), "refresh") == 0
    assert run("--root", str(root), "check") == 0


def edit_model(root: Path, old: str, new: str) -> None:
    model = root / "map/model.py"
    text = model.read_text()
    assert old in text, old
    model.write_text(text.replace(old, new))


# ---- entry: every card is code that exists today --------------------------------


def test_module_not_in_the_facts_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current(tmp_path)
    capsys.readouterr()
    # The writer's module is renamed away in the model: it names code that is not there.
    edit_model(tmp_path, 'implemented_by=("pkg.writer",)', 'implemented_by=("pkg.planner",)')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "entry: 1 problem" in out
    assert "Writer names module pkg.planner which is not in the facts" in out
    assert "fix: in map/model.py, name only modules the facts have" in out
    assert "the map draws what exists today" in out
    # coverage also reports the now unclaimed module, and it outranks the
    # entry rule in the closing line: an unclaimed module is fixed first.
    assert "unmapped: pkg.writer" in out
    assert out.rstrip().endswith("then run: systemap check")
    # The same finding is not reported a second time under stale.
    assert out.count("pkg.planner") == 1


def test_component_with_no_module_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current(tmp_path)
    capsys.readouterr()
    edit_model(tmp_path, 'implemented_by=("pkg.writer",)', "implemented_by=()")
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "Writer names no module; a component is code in the tree" in out


def test_actor_claims_no_code_and_is_not_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    edit_model(
        tmp_path,
        "COMPONENTS = (",
        'COMPONENTS = (\n    Component(id="User", does="Types.", kind="actor", '
        'container="system", x=400, y=24),',
    )
    edit_model(
        tmp_path,
        '"Reader": "the part that reads",',
        '"Reader": "the part that reads", "User": "the person",',
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    assert "entry:" not in capsys.readouterr().out


def test_entry_the_modules_do_not_define_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    edit_model(tmp_path, 'entry="write",', 'entry="publish",')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "entry: 1 problem" in out
    assert "Writer names entry publish which none of its modules defines (pkg.writer)" in out
    assert "set entry to a public name one of them defines" in out


def test_missing_entry_with_modules_present_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    edit_model(tmp_path, 'entry="write",', "")
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "Writer names no entry; its modules are pkg.writer" in out


# ---- stale ---------------------------------------------------------------------


def test_stale_facts_after_a_code_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    (tmp_path / "pkg/reader.py").write_text("def read(source):\n    return 1\n")
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "stale: 1 problem" in out
    assert "facts: code changed since the map was built: pkg.reader" in out
    assert "fix: run: systemap refresh" in out
    assert out.rstrip().endswith("run: systemap refresh")
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0


def test_stale_page_after_a_model_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    edit_model(tmp_path, '"Reader": "the part that reads"', '"Reader": "the reading part"')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "docs/map/index.html differs from what systemap renders" in out
    assert "docs/map/figures/structure.svg differs from what systemap renders" in out
    assert "docs/map/figures/system.svg differs from what systemap renders" in out
    assert "facts:" not in out, "the tree did not change, only the model"
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0


def test_stale_figure_when_missing_or_edited(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    fig = tmp_path / "docs/map/figures/system.svg"
    fig.unlink()
    assert run("--root", str(tmp_path), "check") == 1
    assert "docs/map/figures/system.svg has not been rendered" in capsys.readouterr().out
    assert run("--root", str(tmp_path), "refresh") == 0
    fig.write_text(fig.read_text() + "<!-- by hand -->")
    assert run("--root", str(tmp_path), "check") == 1
    assert "docs/map/figures/system.svg differs from what systemap renders" in (
        capsys.readouterr().out
    )


def test_stale_with_no_facts_names_extract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "no facts have been built yet" in out
    assert out.rstrip().endswith("run: systemap extract")


# ---- the bare figure -----------------------------------------------------------


def test_svg_figure_is_the_bare_drawing_on_its_ground(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "refresh") == 0
    svg = (tmp_path / "docs/map/figures/system.svg").read_text()
    assert svg.startswith('<svg id="lessonmap"')
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert svg.rstrip().endswith("</svg>")
    assert "<figure" not in svg and "<script" not in svg
    assert 'fill="#121417"/>' in svg, "the ground rectangle carries the theme's bg"
    assert svg.index("<rect") < svg.index("<defs>"), "the ground is drawn first"
    assert run("--root", str(tmp_path), "check") == 0
    capsys.readouterr()
    out = tmp_path / "one.svg"
    assert run("--root", str(tmp_path), "figure", "--static", "--out", str(out)) == 0
    assert out.read_text().startswith("<svg ")


# ---- labels: both labels named; headers join the rule ----------------------------


def test_a_label_collision_names_both_labels() -> None:
    """Five labels on one short run have four gutter seats: the fifth lands on one."""
    pts = [(0.0, 50.0), (100.0, 50.0)]
    routes = {i: route.Route(points=list(pts), src_side="right", dst_side="left") for i in range(5)}
    names = {i: f"label 'art{i}' (A -> B)" for i in range(5)}
    placed = route.place_labels(
        routes, dict.fromkeys(routes, 90.0), 13.0, [], (100.0, 100.0), names=names
    )
    hit = [p for p in placed.values() if p.cost > 0]
    assert hit, "four seats for five labels"
    for p in hit:
        assert p.hits and all(h.startswith("label 'art") and "(A -> B)" in h for h in p.hits), (
            p.hits
        )
    # Without names the report falls back to the index.
    placed = route.place_labels(routes, dict.fromkeys(routes, 90.0), 13.0, [], (100.0, 100.0))
    assert any(h.startswith("label ") and h[6:].isdigit() for p in placed.values() for h in p.hits)


def test_header_sub_wraps_to_two_lines_and_is_refused_past_that(sample: Sample) -> None:
    def with_sub(sub: str) -> tuple[str, list[str]]:
        model = dataclasses.replace(
            sample.model,
            containers=tuple(
                dataclasses.replace(c, sub=sub) if c.id == "system" else c
                for c in sample.model.containers
            ),
        )
        svg, detail = render_schematic(model, sample.meaning, sample.theme, sample.facts)
        return svg, check.check_labels(json.loads(detail)["_meta"])

    # The system box is 662 wide: 113 characters fit one line, 226 two.
    two_lines = "one process that " + "reads and writes " * 8
    svg, problems = with_sub(two_lines.strip())
    assert problems == []
    assert "..." not in svg, "a sub that fits wraps; nothing is cut"
    assert svg.count('y="49.0"') + svg.count('y="61.0"') >= 2, "the second line is drawn"
    svg, problems = with_sub(("one process " * 25).strip())
    assert problems == [
        "header of container system: sub does not fit its box (299 characters; 2 lines of 113 fit)"
    ]
    assert "..." not in svg
    svg, problems = with_sub("x" * 120)
    assert problems == [
        "header of container system: sub does not fit its box (120 characters; 2 lines of 113 fit)"
    ]


def test_header_labels_wider_than_the_box_and_headers_on_cards_are_refused(sample: Sample) -> None:
    model = dataclasses.replace(
        sample.model,
        containers=(
            *sample.model.containers[:1],
            Container("narrow", "A VERY MUCH TOO LONG CONTAINER LABEL", (222, 380, 100, 16)),
        ),
        regions=tuple(
            dataclasses.replace(r, label="A REGION LABEL FAR WIDER THAN ITS BAND " * 3)
            if r.id == "keep"
            else r
            for r in sample.model.regions
        ),
    )
    _svg, detail = render_schematic(model, sample.meaning, sample.theme, sample.facts)
    meta = json.loads(detail)["_meta"]
    problems = check.check_labels(meta)
    assert "header of container narrow: label is wider than its box" in problems
    assert "header of region keep: label is wider than its box" in problems
    assert {h["kind"] for h in meta["headers"]} == {"container", "region"}
    # A card placed under a header is touched by it.
    low = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, y=20) if c.id == "Reader" else c for c in sample.model.components
        ),
        regions=tuple(
            dataclasses.replace(r, box=(240, 18, 626, 162)) if r.id == "work" else r
            for r in sample.model.regions
        ),
    )
    _svg, detail = render_schematic(low, sample.meaning, sample.theme, sample.facts)
    problems = check.check_labels(json.loads(detail)["_meta"])
    assert "header of container system touches card Reader" in problems
    assert "header of region work touches card Reader" in problems


def test_header_overflow_fails_check_and_refresh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    edit_model(
        tmp_path,
        'sub="one process; replace this line with what the boundary means",',
        'sub="' + "one process that never stops " * 12 + '",',
    )
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "header of container system: sub does not fit its box" in out
    assert run("--root", str(tmp_path), "refresh") == 1
    assert "map: check failed" in capsys.readouterr().out


# ---- wheel: nothing leaves a drawing that sizes itself ---------------------------


def test_wheel_labels_may_reach_past_the_old_frame(sample: Sample) -> None:
    # Three spokes put one at thirty degrees, where a thirty-character name
    # runs well past the 400-unit frame the old rule refused.
    names = [f"averyveryverylongcomponentname{k}" for k in range(3)]
    edges = [{"from": "Reader", "to": name, "layer": "data"} for name in names]
    _centre, boxes = check.wheel_boxes("Reader", edges, all_layers(sample.model, sample.meaning))
    assert any(x + w > 400 for _name, (x, _y, w, _h) in boxes)
    assert check.check_wheels(edges, sample.model, sample.meaning) == []
    assert not hasattr(check, "W"), "the frame is gone with the rule"


# ---- refresh verifies what it wrote --------------------------------------------


def test_refresh_exits_1_when_the_check_fails_after_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    current(tmp_path)
    (tmp_path / "pkg/reader.py").write_text("def read(source):\n    return 1\n")
    real = check.stale
    calls = {"n": 0}

    def flaky(*args: object, **kwargs: object) -> list[str]:
        calls["n"] += 1
        lines = real(*args, **kwargs)  # type: ignore[arg-type]
        return lines if calls["n"] == 1 else [*lines, "docs/map/index.html differs (simulated)"]

    monkeypatch.setattr(check, "stale", flaky)
    capsys.readouterr()
    assert run("--root", str(tmp_path), "refresh") == 1
    out = capsys.readouterr().out
    assert "stale: 1 problem" in out
    assert "docs/map/index.html differs (simulated)" in out
    assert out.rstrip().endswith("map: check failed after the refresh; run: systemap refresh")
    assert calls["n"] == 2, "the check ran once before writing and once after"


def test_root_is_accepted_after_the_subcommand(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("init", "--root", str(tmp_path), "--no-ci") == 0
    assert (tmp_path / "systemap.toml").is_file()
    (tmp_path / "map/model.py").write_text(TWO_CARD_MODEL)
    assert run("extract", "--root", str(tmp_path)) == 0
    assert run("refresh", "--root", str(tmp_path)) == 0
    assert run("check", "--root", str(tmp_path)) == 0
    out = tmp_path / "fig.svg"
    assert run("figure", "--root", str(tmp_path), "--static", "--out", str(out)) == 0
    assert out.is_file()
    assert run("judgement", "--root", str(tmp_path)) == 0
    assert run("render", "--check", "--root", str(tmp_path)) == 0
    assert run("skill", "--root", str(tmp_path), "--print") == 0
    # Given in both positions, the later one wins; given only before, it still applies.
    capsys.readouterr()
    assert run("--root", str(tmp_path / "nowhere"), "check", "--root", str(tmp_path)) == 0
    assert run("--root", str(tmp_path), "check") == 0
