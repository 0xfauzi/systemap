"""Results of a trial on real Python repositories: the entry rule, the Python adapter,
`history`, and `init`.

Each test uses a small fixture. No test clones a real repository. Acceptance values:

- trial-2: a component that claims a module with no public names passes the entry rule
  in three cases. In a Python fixture, `entry="python -m pkg"` names the `__main__`
  module. In a TypeScript fixture, `entry="web"` names the package bin. A Python script
  with no public names and no entry point has an empty `entry`. Each case gives no
  entry line. Before the repair, each case gave one line. A module with a public name
  and an empty `entry` still gives one line. The `fix:` line tells the reader to use the
  name of an entry point that does not start one public name.
- trial-3: three `def get` statements (two `typing.overload` signatures and one
  implementation) give one public name `get`. Before the repair, they gave three.
  A change to one overload signature is a change of `get` in the public surface. The
  TypeScript adapter gives one public name for overload signatures. It did that before
  the repair.
- trial-17: a console script `pkg:main`, where `pkg` imports `main` from `pkg._main`,
  a `main` function, and a click command on that function give one entry point without
  a sequence: the console script. Before the repair, they gave three. A second module-level
  binding of `main` in `pkg`, outside an `except` clause, keeps the console script
  separate.
- trial-19: `history` on a shallow clone gives the line "history: This repository is a
  shallow clone. Its history starts at the shallow boundary, commit <sha> on <date>."
  A full clone gives no such line.
- trial-20: `init` prints the deptry lines only if a repository file names deptry.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_change_git import GIT, commit, make

from systemap import change, check, config, extract, history, journey_coverage, scaffold
from systemap.cli import main
from systemap.extract import PYTHON
from systemap.model import Component, Meaning, Model, Region
from systemap.source_facts import entry_identity
from systemap.typescript import TYPESCRIPT

# ---- trial-2: the entry rule for a module that defines no public name -------------


def _model(*components: Component) -> Model:
    return Model(
        canvas=(0, 0),
        containers=(),
        regions=(Region(id="core", label="CORE", box=(0, 0, 0, 0)),),
        components=components,
        flows=(),
        flow_kinds=(),
    )


def _facts(root: Path, files: dict[str, str]) -> dict[str, Any]:
    write_tree(root, files)
    return extract.build(config.load(root))


PY_SCRIPT = {
    "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
    "pkg/__main__.py": "import sys\n\nprint(sys.argv)\n",
    "pkg/script.py": "import sys\n\nprint(len(sys.argv))\n",
    "pkg/tools.py": "def run() -> None:\n    pass\n",
}
TS_BIN = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web","bin":{"web":"src/cli.ts"}}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/cli.ts": 'console.log("start");\n',
    "src/index.ts": "export function serve(): void {}\n",
}


def _card(module: str, entry: str) -> Component:
    return Component("Cli", "Starts a run.", implemented_by=(module,), entry=entry, region="core")


def test_a_main_module_without_public_names_can_be_the_entry(tmp_path: Path) -> None:
    facts = _facts(tmp_path, PY_SCRIPT)
    assert check.check_entry(_model(_card("pkg.__main__", "python -m pkg")), facts) == []
    # The entry point exists, so an empty entry still gives a line.
    assert check.check_entry(_model(_card("pkg.__main__", "")), facts) == [
        "Cli has no entry. Its modules are pkg.__main__"
    ]


def test_a_script_without_public_names_or_entry_points_needs_no_entry(tmp_path: Path) -> None:
    facts = _facts(tmp_path, PY_SCRIPT)
    assert check.check_entry(_model(_card("pkg.script", "")), facts) == []
    # A module with a public name still must have an entry.
    assert check.check_entry(_model(_card("pkg.tools", "")), facts) == [
        "Cli has no entry. Its modules are pkg.tools"
    ]
    # A name that is not an entry point of the module is not an entry.
    assert check.check_entry(_model(_card("pkg.script", "python -m pkg")), facts) == [
        "Cli has entry python -m pkg, but its modules do not define this entry (pkg.script)."
    ]


def test_a_module_that_did_not_parse_still_must_have_an_entry(tmp_path: Path) -> None:
    facts = _facts(tmp_path, {**PY_SCRIPT, "pkg/script.py": "def broken(:\n"})
    assert check.check_entry(_model(_card("pkg.script", "")), facts) == [
        "Cli has no entry. Its modules are pkg.script"
    ]


def test_a_typescript_bin_without_exports_can_be_the_entry(tmp_path: Path) -> None:
    facts = _facts(tmp_path, TS_BIN)
    assert check.check_entry(_model(_card("web.cli", "web")), facts) == []
    assert check.check_entry(_model(_card("web.cli", "")), facts) == [
        "Cli has no entry. Its modules are web.cli"
    ]


def test_the_entry_fix_line_names_an_action_for_a_module_without_names() -> None:
    coverage = check.Coverage(checked=False, mapped=0, total=0, ignored=0, problems=())
    result = check.Result(
        problems=[],
        through=0,
        across=0,
        coverage=coverage,
        entry=["Cli has no entry. Its modules are pkg.__main__"],
    )
    text = "\n".join(check.report(_model(), result, teach=False))
    assert (
        "If an entry point does not start one public name, set entry to its name from systemap facts --entry-points."
        in text
    )


# ---- trial-3: overload signatures give one public name ------------------------------

OVERLOADS = """
from typing import overload


@overload
def get(x: int) -> int: ...
@overload
def get(x: str) -> str: ...
def get(x):
    return x
"""


def test_python_overloads_give_one_public_name() -> None:
    surface = PYTHON.parse_surface(OVERLOADS)
    assert surface is not None
    assert surface["names"] == [{"name": "get", "kind": "function"}]


def test_a_changed_python_overload_signature_changes_the_name() -> None:
    changed = OVERLOADS.replace("def get(x: str) -> str", "def get(x: bytes) -> bytes")
    delta = change.surface_delta(OVERLOADS, changed, PYTHON)
    assert delta is not None
    assert delta["changed"]["operations"] == ["get"]


TS_OVERLOADS = (
    "export function get(x: number): number;\n"
    "export function get(x: string): string;\n"
    "export function get(x: any): any { return x; }\n"
)


def test_typescript_overloads_give_one_public_name() -> None:
    surface = TYPESCRIPT.parse_surface(TS_OVERLOADS, "src/get.ts")
    assert surface is not None
    assert surface["names"] == [{"name": "get", "kind": "function"}]
    changed = TS_OVERLOADS.replace("get(x: string): string", "get(x: boolean): boolean")
    delta = change.surface_delta(TS_OVERLOADS, changed, TYPESCRIPT, "src/get.ts")
    assert delta is not None
    assert delta["changed"]["operations"] == ["get"]


# ---- trial-17: one CLI function gives one entry point -------------------------------

CLICK_MAIN = "import click\n\n\n@click.command()\ndef main() -> None:\n    print('run')\n"
ROOT_IMPORT = (
    "try:\n"
    "    from pkg._main import main\n"
    "except ImportError:\n\n"
    "    def main() -> None:\n"
    "        print('The command needs click.')\n"
)


def _cli_points(
    root: Path, init: str, main_source: str = CLICK_MAIN
) -> tuple[list[dict[str, str]], list[str]]:
    facts = _facts(
        root,
        {
            "pyproject.toml": (
                '[project]\nname = "pkg"\nversion = "0"\n[project.scripts]\ntool = "pkg:main"\n'
            ),
            "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
            "pkg/__init__.py": init,
            "pkg/_main.py": main_source,
        },
    )
    missing = journey_coverage.ways_in_without_journey(Meaning(plain={}), facts)
    return facts["entry_points"], [p["name"] for p in missing]


def test_one_cli_function_gives_one_entry_point(tmp_path: Path) -> None:
    points, missing = _cli_points(tmp_path, ROOT_IMPORT)
    assert sorted(p["kind"] for p in points) == ["command", "console_script", "main_function"]
    assert missing == ["tool"]
    script = next(p for p in points if p["kind"] == "console_script")
    assert all(p["same_as"] == entry_identity(script) for p in points if p is not script)
    assert script["same_as"] == ""


def test_a_second_binding_keeps_the_console_script_separate(tmp_path: Path) -> None:
    init = "from pkg._main import main\n\nif len(__name__) > 3:\n\n    def main() -> None:\n        pass\n"
    points, missing = _cli_points(tmp_path, init)
    assert missing == ["tool", "main"]
    by_kind = {p["kind"]: p for p in points}
    assert by_kind["console_script"]["same_as"] == ""
    assert by_kind["main_function"]["same_as"] == ""
    assert by_kind["command"]["same_as"] == entry_identity(by_kind["main_function"])


def test_a_command_on_a_different_function_is_a_different_entry_point(tmp_path: Path) -> None:
    source = (
        CLICK_MAIN.replace("def main()", "def serve()") + "\n\ndef main() -> None:\n    serve()\n"
    )
    points, missing = _cli_points(tmp_path, ROOT_IMPORT, source)
    assert missing == ["tool", "serve"]
    assert {p["kind"]: p["same_as"] for p in points}["command"] == ""


# ---- trial-19: history on a shallow clone -------------------------------------------


def _dated_repo(root: Path, days: list[str]) -> None:
    root.mkdir(parents=True)
    subprocess.run([*GIT, "init", "-q", str(root)], check=True)
    for k, day in enumerate(days):
        (root / "a.txt").write_text(str(k), encoding="utf-8")
        env = {"GIT_AUTHOR_DATE": f"{day}T12:00:00", "GIT_COMMITTER_DATE": f"{day}T12:00:00"}
        subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True)
        subprocess.run(
            [*GIT, "-C", str(root), "commit", "-qm", f"c{k}"],
            check=True,
            env={**_environment(), **env},
        )


def _environment() -> dict[str, str]:
    import os

    return dict(os.environ)


def test_a_shallow_clone_tells_where_the_history_starts(tmp_path: Path) -> None:
    _dated_repo(tmp_path / "full", ["2024-01-05", "2024-03-10", "2024-05-20", "2024-07-01"])
    shallow = tmp_path / "shallow"
    url = (tmp_path / "full").as_uri()
    subprocess.run([*GIT, "clone", "-q", "--depth", "2", url, str(shallow)], check=True)
    shas = history.sample(shallow, "2020-01-01", 1)
    assert len(shas) == 2
    boundary = shas[0]
    assert history.shallow_note(shallow, shas) == [
        f"history: This repository is a shallow clone. Its history starts at the shallow "
        f"boundary, commit {boundary[:12]} on 2024-05-20."
    ]
    full_shas = history.sample(tmp_path / "full", "2020-01-01", 1)
    assert history.shallow_note(tmp_path / "full", full_shas) == []


def test_history_prints_the_shallow_boundary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(tmp_path / "repo", "python")
    (root / "pkg/extra.py").write_text("X = 1\n", encoding="utf-8")
    commit(root, "add a module")
    shallow = tmp_path / "shallow"
    subprocess.run([*GIT, "clone", "-q", "--depth", "1", root.as_uri(), str(shallow)], check=True)
    capsys.readouterr()
    assert main(["--root", str(shallow), "history"]) == 0
    out = capsys.readouterr().out
    assert "history: This repository is a shallow clone." in out


# ---- trial-20: the deptry lines of init ---------------------------------------------

STARTER = {"pkg/__init__.py": "", "pkg/reader.py": "def read() -> None:\n    pass\n"}
PYPROJECT = '[project]\nname = "pkg"\nversion = "0"\n'


@pytest.mark.parametrize(
    ("files", "deptry"),
    [
        ({}, False),
        ({"pyproject.toml": PYPROJECT}, False),
        ({"pyproject.toml": PYPROJECT + "\n[tool.deptry]\nexclude = []\n"}, True),
        (
            {
                "pyproject.toml": PYPROJECT,
                ".pre-commit-config.yaml": "repos:\n  - repo: https://github.com/fpgmaas/deptry\n",
            },
            True,
        ),
    ],
)
def test_init_prints_the_deptry_lines_only_for_a_repository_that_uses_deptry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], files: dict[str, str], deptry: bool
) -> None:
    write_tree(tmp_path, {**STARTER, **files})
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    out = capsys.readouterr().out
    assert ("[tool.deptry.per_rule_ignores]" in out) is deptry
    assert "mypy --strict" in out
    assert scaffold.uses_deptry(tmp_path) is deptry


def test_the_deptry_note_reads_only_regular_files_in_the_repository(tmp_path: Path) -> None:
    """A link out of the repository and a FIFO are not read.

    Acceptance: a `tox.ini` link to a file outside the repository with the word deptry
    gives False, and a FIFO `Makefile` gives False with no wait.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.ini"
    outside.write_text("[testenv]\ncommands = deptry .\n", encoding="utf-8")
    (repo / "tox.ini").symlink_to(outside)
    assert scaffold.uses_deptry(repo) is False
    if hasattr(os, "mkfifo"):
        os.mkfifo(repo / "Makefile")
        assert scaffold.uses_deptry(repo) is False
