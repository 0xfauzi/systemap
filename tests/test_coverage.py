"""The coverage rule of `systemap check`, driven through the CLI.

Every case starts from what `systemap init` writes: a package `pkg` with a
reader and a writer, and a starter model claiming `pkg.reader` and
`pkg.writer`. The package root `pkg` is an empty `__init__`: an empty
package marker, which the rule leaves out on its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import init_two_cards, write_tree

from systemap import extract
from systemap.cli import main

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def scaffold(root: Path) -> None:
    """init and one refresh, so the map is current before a case breaks it."""
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root)
    assert run("--root", str(root), "refresh") == 0


def ignore(root: Path, *entries: str) -> None:
    toml = root / "systemap.toml"
    body = "".join(f"    {entry},\n" for entry in entries)
    toml.write_text(toml.read_text() + f"\n[coverage]\nignore = [\n{body}]\n")


def test_all_mapped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    assert run("--root", str(tmp_path), "check") == 0
    out = capsys.readouterr().out
    assert "coverage: 3 of 3 modules mapped, 1 of them an empty package marker" in out
    assert "unmapped" not in out


def test_one_unmapped_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    write_tree(tmp_path, {"pkg/extra.py": "def extra() -> None:\n    pass\n"})
    assert run("--root", str(tmp_path), "extract") == 0
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "coverage: 3 of 4 modules mapped, 1 of them an empty package marker" in out
    assert "unmapped: pkg.extra (no component claims it)" in out
    assert "map layout: clean" in out, "the layout is fine; only coverage failed"
    assert "map every module in map/model.py, or ignore it with a reason" in out
    # refresh runs the same check and refuses too.
    assert run("--root", str(tmp_path), "refresh") == 1
    assert "map: check failed" in capsys.readouterr().out


def test_ignore_with_reason_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    write_tree(tmp_path, {"pkg/extra.py": "def extra() -> None:\n    pass\n"})
    assert run("--root", str(tmp_path), "extract") == 0
    ignore(tmp_path, '{ module = "pkg.extra", reason = "a scratch file with no place on the map" }')
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    assert (
        "coverage: 4 of 4 modules mapped, 1 of them ignored with a reason, "
        "1 of them an empty package marker"
    ) in capsys.readouterr().out


def test_ignore_without_reason_is_a_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    toml = tmp_path / "systemap.toml"
    kept = toml.read_text()
    ignore(tmp_path, '{ module = "pkg.extra" }')
    assert run("--root", str(tmp_path), "check") == 2
    err = capsys.readouterr().err
    assert "coverage.ignore[1] (pkg.extra) needs a reason" in err

    toml.write_text(kept)
    ignore(tmp_path, '{ module = "pkg.extra", reason = "  " }')
    assert run("--root", str(tmp_path), "check") == 2
    assert "needs a reason" in capsys.readouterr().err

    toml.write_text(kept)
    ignore(tmp_path, '{ module = "pkg.extra", reason = "x", why = "y" }')
    assert run("--root", str(tmp_path), "check") == 2
    assert "coverage.ignore[1] has unknown key: why" in capsys.readouterr().err


def test_double_claim_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    model = tmp_path / "map/model.py"
    model.write_text(
        model.read_text().replace(
            'implemented_by=("pkg.writer",)', 'implemented_by=("pkg.writer", "pkg.reader")'
        )
    )
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "coverage: 2 of 3 modules mapped, 1 of them an empty package marker" in out
    assert "claimed twice: pkg.reader (Reader, Writer)" in out


def test_subtree_claim_covers_the_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    # A subpackage appears; the reader claims it whole with one `.*` entry,
    # its marker included: a claimed marker is mapped, not left out.
    write_tree(
        tmp_path,
        {"pkg/sub/__init__.py": "", "pkg/sub/deep.py": "def deep() -> None:\n    pass\n"},
    )
    model = tmp_path / "map/model.py"
    text = model.read_text()
    text = text.replace(
        'implemented_by=("pkg.reader",)', 'implemented_by=("pkg.reader", "pkg.sub.*")'
    )
    model.write_text(text)
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    assert "coverage: 5 of 5 modules mapped, 1 of them an empty package marker" in (
        capsys.readouterr().out
    )


def test_stale_ignore_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    ignore(tmp_path, '{ module = "pkg.gone", reason = "it left" }')
    assert run("--root", str(tmp_path), "check") == 1
    assert "ignore names a module the facts do not have: pkg.gone" in capsys.readouterr().out


def test_no_facts_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path)
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "coverage: not checked, there are no facts; run: systemap extract" in out
    assert out.rstrip().endswith("run: systemap extract")


# ---- empty package markers, and the subtree ignore -----------------------------------


def test_empty_package_markers_are_left_out_and_listed_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nine empty __init__ files once needed nine ignore entries; now none."""
    scaffold(tmp_path)
    write_tree(
        tmp_path,
        {
            "pkg/sub/__init__.py": "",
            "pkg/sub/deep.py": "def deep() -> None:\n    pass\n",
            "pkg/other/__init__.py": '"""A docstring alone is still a marker."""\n',
        },
    )
    model = tmp_path / "map/model.py"
    model.write_text(
        model.read_text().replace(
            'implemented_by=("pkg.reader",)', 'implemented_by=("pkg.reader", "pkg.sub.deep")'
        )
    )
    capsys.readouterr()
    assert run("--root", str(tmp_path), "extract") == 0
    out = capsys.readouterr().out
    assert (
        "  empty package markers: 3 (pkg, pkg.other, pkg.sub); an __init__ with no public "
        "names and no imports, left out of the coverage rule"
    ) in out
    assert out.count("empty package markers") == 1, "listed once"
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    assert "coverage: 6 of 6 modules mapped, 3 of them empty package markers" in (
        capsys.readouterr().out
    )
    facts = extract.read_facts(tmp_path / "docs/map/map.json")
    assert extract.empty_markers(facts) == ["pkg", "pkg.other", "pkg.sub"]
    assert extract.is_empty_marker(facts["components"]["pkg.sub"])
    assert not extract.is_empty_marker(facts["components"]["pkg.sub.deep"])


def test_an_init_that_imports_or_defines_is_not_a_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    write_tree(
        tmp_path,
        {
            "pkg/sub/__init__.py": "from pkg.sub.deep import deep\n",
            "pkg/sub/deep.py": "def deep() -> None:\n    pass\n",
            # A third-party import counts; the standard library is not in the facts.
            "pkg/ext/__init__.py": "import yaml\n",
            "pkg/named/__init__.py": "NAME = 1\n",
        },
    )
    assert run("--root", str(tmp_path), "extract") == 0
    capsys.readouterr()
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    for module in ("pkg.sub", "pkg.sub.deep", "pkg.ext", "pkg.named"):
        assert f"unmapped: {module} (no component claims it)" in out, module
    assert "coverage: 3 of 7 modules mapped, 1 of them an empty package marker" in out
    facts = extract.read_facts(tmp_path / "docs/map/map.json")
    assert extract.empty_markers(facts) == ["pkg"]


def test_an_ignore_that_names_only_markers_is_not_needed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    ignore(tmp_path, '{ module = "pkg", reason = "the package root only marks the directory" }')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert (
        "ignore is not needed: pkg is an empty package marker, left out of the coverage "
        "rule on its own; remove the entry"
    ) in out
    assert "coverage: 3 of 3 modules mapped, 1 of them an empty package marker" in out


def test_subtree_ignore_glob(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`module = "pkg.sub.*"` ignores the subtree; its marker is a marker, the rest ignored."""
    scaffold(tmp_path)
    write_tree(
        tmp_path,
        {
            "pkg/sub/__init__.py": "",
            "pkg/sub/deep.py": "def deep() -> None:\n    pass\n",
            "pkg/sub/deeper.py": "def deeper() -> None:\n    pass\n",
        },
    )
    assert run("--root", str(tmp_path), "extract") == 0
    ignore(
        tmp_path, '{ module = "pkg.sub.*", reason = "a vendored subtree with no place on the map" }'
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    assert (
        "coverage: 6 of 6 modules mapped, 2 of them ignored with a reason, "
        "2 of them empty package markers"
    ) in capsys.readouterr().out
