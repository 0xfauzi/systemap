"""The entry and stale rules of `systemap check`, and the bare figure.

Every case starts from what `systemap init` writes and refreshes once, so
the map is current, and then breaks exactly one thing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_tree

from systemap.cli import main

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def current(root: Path) -> None:
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(root), "init", "--no-ci") == 0
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
    assert "set entry to a public function or class one of them defines" in out


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
    assert "docs/map/system.html differs from what systemap renders" in out
    assert "facts:" not in out, "the tree did not change, only the model"
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0


def test_stale_figure_when_missing_or_edited(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    fig = tmp_path / "docs/map/system.html"
    fig.unlink()
    assert run("--root", str(tmp_path), "check") == 1
    assert "docs/map/system.html has not been rendered" in capsys.readouterr().out
    assert run("--root", str(tmp_path), "refresh") == 0
    fig.write_text(fig.read_text() + "<!-- by hand -->")
    assert run("--root", str(tmp_path), "check") == 1
    assert "docs/map/system.html differs from what systemap renders" in capsys.readouterr().out


def test_stale_with_no_facts_names_extract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "no facts have been built yet" in out
    assert out.rstrip().endswith("run: systemap extract")


# ---- the bare figure -----------------------------------------------------------


def test_svg_figure_is_the_bare_drawing_on_its_ground(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text().replace(
            'out = "system.html"\nmode = "system"\ninteractive = true',
            'out = "figures/system.svg"\nmode = "system"\ninteractive = false',
        )
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    svg = (tmp_path / "docs/map/figures/system.svg").read_text()
    assert svg.startswith('<svg id="lessonmap"')
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert svg.rstrip().endswith("</svg>")
    assert "<figure" not in svg and "<script" not in svg
    assert 'fill="#0b1020"/>' in svg, "the ground rectangle carries the theme's bg"
    assert svg.index("<rect") < svg.index("<defs>"), "the ground is drawn first"
    assert run("--root", str(tmp_path), "check") == 0
    capsys.readouterr()
    out = tmp_path / "one.svg"
    assert run("--root", str(tmp_path), "figure", "--static", "--out", str(out)) == 0
    assert out.read_text().startswith("<svg ")
