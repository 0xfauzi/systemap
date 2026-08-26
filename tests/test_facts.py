"""Re-exports in the facts, and `systemap facts`: the file read back one view at a time.

A re-exporting `__init__` once recorded no names, so a package's public
face could not be a card's entry; and the facts file, hundreds of
kilobytes on a real tree, was what the skill told the agent to read.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import TINY_PACKAGE, init_two_cards, write_tree

from systemap import check, config, extract, skill
from systemap import facts as facts_mod
from systemap.cli import main
from systemap.model import Component, Model, defines_entry, public_names

REEXPORT_TREE: dict[str, str] = {
    "pkg/__init__.py": (
        "from pkg.core import run, Thing, Thing as Item, _hidden\n"
        "from .sub import deep\n"
        "from . import util\n"
        "from pkg.core import *\n"
        "from typing import Any\n"
        "import os\n"
        "\n"
        "VERSION = '1'\n"
    ),
    "pkg/core.py": (
        "class Thing:\n    def go(self) -> None:\n        pass\n\n\n"
        "def run() -> None:\n    pass\n\n\ndef _hidden() -> None:\n    pass\n"
    ),
    "pkg/sub.py": "def deep() -> None:\n    pass\n",
    "pkg/util.py": "from pkg.core import run\n\n\ndef helper() -> None:\n    run()\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def test_a_package_init_records_the_names_it_reexports(tmp_path: Path) -> None:
    write_tree(tmp_path, REEXPORT_TREE)
    facts = extract.build(config.load(tmp_path))
    root = facts["components"]["pkg"]
    assert root["names"] == [
        {"name": "run", "kind": "function", "reexport_of": "pkg.core"},
        {"name": "Thing", "kind": "class", "reexport_of": "pkg.core"},
        {"name": "Item", "kind": "class", "reexport_of": "pkg.core"},
        {"name": "deep", "kind": "function", "reexport_of": "pkg.sub"},
        {"name": "util", "kind": "module", "reexport_of": "pkg.util"},
        {"name": "VERSION", "kind": "constant"},
    ]
    # A private name, a star import and anything outside the package are not re-exports.
    assert public_names(root) == {"run", "Thing", "Item", "deep", "util", "VERSION"}
    assert root["functions"] == [] and root["classes"] == []
    assert not extract.is_empty_marker(root), "a re-exporting __init__ is a module"
    # A plain module's imports stay imports: only a package __init__ re-exports.
    assert facts["components"]["pkg.util"]["names"] == [{"name": "helper", "kind": "function"}]
    # No public function is invented for the package root's entry points.
    assert [p["name"] for p in facts["entry_points"]] == []
    # A card may name a re-export as its entry, and start its interface with
    # one; the methods of a re-exported class are read from the module that
    # defines it. An alias hides the class from that lookup.
    card = Component(
        "Core", "the core", implemented_by=("pkg",), entry="Item", interface="Thing.go()"
    )
    assert defines_entry(card, facts)

    def with_interface(text: str) -> Model:
        return Model(
            canvas=(600, 200),
            containers=(),
            regions=(),
            components=(dataclasses.replace(card, interface=text),),
            flows=(),
            flow_kinds=(),
        )

    assert check.check_interface(with_interface("Thing.go()"), facts) == []
    assert check.check_interface(with_interface("run() -> None"), facts) == []
    assert check.check_interface(with_interface("Item.go()"), facts) == [
        "Core interface names Item.go, but Item has no public method go (pkg); closest: Thing"
    ]


def test_reexport_resolution_and_relative_sources() -> None:
    surface = extract.parse_surface(
        "from ..top import a\nfrom .b import c as d\nfrom pkg.x import e\nfrom other import f\n",
        module="pkg.sub",
        is_package=True,
        prefixes=frozenset({"pkg"}),
    )
    assert surface is not None
    assert surface["names"] == [
        {"name": "a", "kind": "reexport", "reexport_of": "pkg.top"},
        {"name": "d", "kind": "reexport", "reexport_of": "pkg.sub.b", "defined_as": "c"},
        {"name": "e", "kind": "reexport", "reexport_of": "pkg.x"},
    ]
    # Without the package flag nothing is a re-export, so the change detector
    # (which parses a blob with no module name) sees the surface it always saw.
    plain = extract.parse_surface("from pkg.x import e\n")
    assert plain is not None and plain["names"] == []
    components = {
        "pkg": {"names": [{"name": "e", "kind": "reexport", "reexport_of": "pkg.x"}]},
        "pkg.x": {"names": [{"name": "e", "kind": "error"}]},
        "pkg.y": {"names": [{"name": "gone", "kind": "reexport", "reexport_of": "pkg.nowhere"}]},
    }
    extract.resolve_reexports(components)
    assert components["pkg"]["names"][0]["kind"] == "error"
    assert components["pkg.y"]["names"][0] == {
        "name": "gone",
        "kind": "object",
        "reexport_of": "pkg.nowhere",
    }


def test_facts_format_is_2_and_an_older_file_is_stale(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    cfg = config.load(tmp_path)
    fresh = extract.build(cfg)
    assert fresh["version"] == extract.FORMAT == 2
    older = {**fresh, "version": 1}
    assert extract.drift(fresh, older) == [
        "facts format 1 is older than the extractor's 2; the file records less than the "
        "extractor reads"
    ]
    assert extract.drift(fresh, fresh) == []


# ---- systemap facts ----------------------------------------------------------------


def test_facts_command_views(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    write_tree(
        tmp_path,
        {
            "pkg/writer.py": (
                "import yaml\nfrom pkg import reader\nfrom pkg.reader import Request\n\n\n"
                "def write(request: Request) -> str:\n    return reader.LIMIT * 'x'\n"
            )
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    capsys.readouterr()
    # No facts yet: the fix is named.
    assert run("--root", str(tmp_path), "facts", "--modules") == 1
    assert capsys.readouterr().out == "no facts at docs/map/map.json\nrun: systemap extract\n"
    assert run("--root", str(tmp_path), "extract") == 0
    capsys.readouterr()

    assert run("--root", str(tmp_path), "facts") == 0
    out = capsys.readouterr().out
    assert out.startswith("facts for the change detector (these never appear on the map):\n")
    assert out.rstrip().endswith(facts_mod.VIEWS)

    assert run("--root", str(tmp_path), "facts", "--modules") == 0
    out = capsys.readouterr().out
    assert out == (
        "modules: 3; each with its public names, imports and tests\n"
        "  pkg: empty package marker\n"
        "  pkg.reader: 4 names, 0 imports, 2 tests\n"
        "  pkg.writer: 1 names, 1 imports, 1 tests\n"
    )

    assert run("--root", str(tmp_path), "facts", "--module", "pkg.reader") == 0
    record = json.loads(capsys.readouterr().out)
    assert record["id"] == "pkg.reader"
    assert record["functions"][0]["signature"] == "def read(source: str) -> Request"
    assert run("--root", str(tmp_path), "facts", "--module", "pkg.reder") == 1
    assert capsys.readouterr().out == (
        "no module pkg.reder in the facts; closest: pkg.reader\nrun: systemap facts --modules\n"
    )

    assert run("--root", str(tmp_path), "facts", "--entry-points") == 0
    out = capsys.readouterr().out
    assert out.startswith("entry points: 0; a journey names each that matters\n")

    assert run("--root", str(tmp_path), "facts", "--external") == 0
    assert capsys.readouterr().out == (
        "external imports: 1; the model sdk line reads these\n  yaml: pkg.writer\n"
    )

    assert run("--root", str(tmp_path), "facts", "--imports", "pkg.writer") == 0
    assert capsys.readouterr().out == (
        "pkg.writer imports 1 modules of the package\n"
        "  pkg.reader (the whole module)\n"
        "pkg.writer is imported by 0 modules of the package\n"
    )
    assert run("--root", str(tmp_path), "facts", "--imports", "pkg.reader") == 0
    assert capsys.readouterr().out == (
        "pkg.reader imports 0 modules of the package\n"
        "pkg.reader is imported by 1 modules of the package\n"
        "  pkg.writer\n"
    )
    # The views are exclusive.
    with pytest.raises(SystemExit):
        run("--root", str(tmp_path), "facts", "--modules", "--external")


def test_the_skill_reads_the_facts_through_the_command() -> None:
    text = skill.text()
    step = text[text.index("1. **extract**") : text.index("2. **draft**")]
    assert "systemap facts" in step and "never the JSON" in step
    for view in (
        "--modules",
        "--module\n   NAME",
        "--entry-points",
        "--external",
        "--imports NAME",
    ):
        assert view in step, view
    assert "`systemap.toml` exists but\n   the facts file does not" in step
    assert "| `systemap facts` |" in text
    pitfalls = skill.files()["references/pitfalls.md"]
    assert "## Reading the facts file whole" in pitfalls
    assert "systemap facts" in pitfalls
