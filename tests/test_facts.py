"""Re-exports in the facts, and `systemap facts`: the file read back one view at a time.

A re-exporting `__init__` once recorded no names, so a package's public
face could not be a card's entry; and the facts file, hundreds of
kilobytes on a real tree, was what the skill told the agent to read.
"""

from __future__ import annotations

import dataclasses
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

    # One line per module: the docstring's first sentence, then the counts.
    assert run("--root", str(tmp_path), "facts", "--modules") == 0
    out = capsys.readouterr().out
    assert out == (
        "modules: 3; each with the first sentence of its docstring, then its public names, "
        "imports and tests counted\n"
        "  pkg: empty package marker\n"
        "  pkg.reader: Read things. (4 names, 0 imports, 2 tests)\n"
        "  pkg.writer: no docstring (1 name, 1 import, 1 test)\n"
    )
    assert run("--root", str(tmp_path), "facts", "--docstrings") == 0
    assert capsys.readouterr().out == (
        "docstrings: 2 of 3 modules have one; the first sentence of each\n"
        "  pkg: empty package marker\n"
        "  pkg.reader: Read things.\n"
        "  pkg.writer: no docstring\n"
    )

    # One record, rendered: never the JSON, and never a test's name.
    assert run("--root", str(tmp_path), "facts", "--module", "pkg.reader") == 0
    out = capsys.readouterr().out
    assert out == (
        "pkg.reader (pkg/reader.py)\n"
        "  docstring: Read things.\n"
        "  public names: 4\n"
        "    LIMIT: constant\n"
        "    Request: class\n"
        "    ReadError: error\n"
        "    read: function\n"
        "  imports: nothing from the package\n"
        "  imported by: pkg.writer\n"
        "  external: none\n"
        "  tests: 2 import it (2 in a file named after it)\n"
    )
    assert "test_read_returns_request" not in out and "{" not in out
    assert run("--root", str(tmp_path), "facts", "--module", "pkg.writer") == 0
    out = capsys.readouterr().out
    assert "  docstring: no docstring\n" in out
    assert "  imports: pkg.reader\n  imported by: nothing in the package\n  external: yaml\n" in out
    assert out.endswith("  tests: 1 import it (0 in a file named after it)\n")
    assert run("--root", str(tmp_path), "facts", "--module", "pkg") == 0
    assert capsys.readouterr().out == (
        "pkg (pkg/__init__.py)\n"
        "  empty package marker: an __init__ with no public names and no imports\n"
    )
    assert run("--root", str(tmp_path), "facts", "--module", "pkg.reder") == 1
    assert capsys.readouterr().out == (
        "no module pkg.reder in the facts; closest: pkg.reader\nrun: systemap facts --modules\n"
    )

    # The public names with their kinds, for entry and interface.
    assert run("--root", str(tmp_path), "facts", "--names", "pkg.reader") == 0
    assert capsys.readouterr().out == (
        "pkg.reader: 4 public names\n"
        "  LIMIT: constant\n"
        "  Request: class\n"
        "  ReadError: error\n"
        "  read: function\n"
    )
    assert run("--root", str(tmp_path), "facts", "--names", "pkg.reder") == 1
    assert "closest: pkg.reader" in capsys.readouterr().out

    assert run("--root", str(tmp_path), "facts", "--entry-points") == 0
    out = capsys.readouterr().out
    assert out.startswith("entry points: 0; a journey names each that matters; the target is ")

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
    with pytest.raises(SystemExit):
        run("--root", str(tmp_path), "facts", "--docstrings", "--names", "pkg")


def test_entry_points_view_prints_the_target_beside_each() -> None:
    """The target is what collapses `python -m pkg`, `main()` and the console
    script into one journey; the view prints it so the reader can see that."""
    facts = {
        "entry_points": [
            {"kind": "console_script", "name": "pkg", "module": "pkg.cli", "target": "main"},
            {"kind": "main_function", "name": "main", "module": "pkg.cli", "target": "main"},
            {
                "kind": "main_module",
                "name": "python -m pkg",
                "module": "pkg.__main__",
                "target": "",
            },
            {"kind": "subcommand", "name": "init", "module": "pkg.cli", "target": "pkg"},
            {"kind": "public_function", "name": "open_thing", "module": "pkg", "target": ""},
        ]
    }
    assert facts_mod.entry_points(facts) == [
        "entry points: 5; a journey names each that matters; the target is the function a "
        "console script calls, or the script a subcommand belongs to",
        "  pkg (console script): pkg.cli, target main",
        "  main() in pkg.cli: pkg.cli, target main",
        "  python -m pkg: pkg.__main__",
        "  pkg init (subcommand): pkg.cli, target pkg",
        "  open_thing() in pkg: pkg",
    ]


def test_names_and_first_sentence_read_old_and_new_records() -> None:
    """A re-export says which module defines it; a facts file from before
    `names` was recorded offers its functions, classes, errors and constants."""
    new = {
        "names": [
            {"name": "run", "kind": "function", "reexport_of": "pkg.core"},
            {"name": "util", "kind": "module", "reexport_of": "pkg.util"},
            {"name": "VERSION", "kind": "constant"},
        ]
    }
    assert facts_mod.kinds(new) == [
        ("run", "function, re-exported from pkg.core"),
        ("util", "module, re-exported from pkg.util"),
        ("VERSION", "constant"),
    ]
    old = {
        "functions": [{"name": "read"}],
        "classes": [{"name": "Request"}],
        "errors": [{"name": "ReadError"}],
        "constants": [{"name": "LIMIT"}],
    }
    assert facts_mod.kinds(old) == [
        ("read", "function"),
        ("Request", "class"),
        ("ReadError", "error"),
        ("LIMIT", "constant"),
    ]
    assert facts_mod.first_sentence("Reads the input. Then more.") == "Reads the input."
    assert facts_mod.first_sentence("Reads  the\n input") == "Reads the input"
    assert facts_mod.first_sentence("Is it read? Yes.") == "Is it read?"
    assert facts_mod.first_sentence("") == "" and facts_mod.first_sentence("  ") == ""


def test_the_skill_reads_the_facts_through_the_command() -> None:
    text = skill.text()
    step = text[text.index("1. **extract**") : text.index("2. **draft**")]
    assert "systemap facts" in step and "never the JSON" in step
    # Every view, and what each gives, in the step.
    for view in (
        "`--modules`, one line per module with the first\n   sentence of its docstring",
        "`--docstrings`, the first sentence alone, for `does`",
        "`--module NAME`,\n   one record rendered",
        "`--names NAME`, its public names with\n   kinds, for `entry` and `interface`",
        "`--entry-points`, where a run\n   starts, each with its target",
        "`--external`, every third-party import\n   and who imports it",
        "`--imports NAME`, what a module imports and what\n   imports it",
    ):
        assert view in step, view
    row = text[text.index("| `systemap facts` |") :].split("\n")[0]
    for view in ("--modules", "--docstrings", "--module NAME", "--names NAME", "--entry-points"):
        assert view in row, view
    assert "`systemap.toml` exists but\n   the facts file does not" in step
    assert "| `systemap facts` |" in text
    pitfalls = skill.files()["references/pitfalls.md"]
    assert "## Reading the facts file whole" in pitfalls
    assert "systemap facts" in pitfalls
    assert "`--docstrings`" in pitfalls and "`--names NAME`" in pitfalls
    assert "none of them prints a test's name" in pitfalls
