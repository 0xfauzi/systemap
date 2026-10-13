"""Repairs of the second Codex review of the Python adapter and the shared source facts
(py-adapter-1 to py-adapter-14).

Each acceptance value is in the docstring of its test. Where the behavior applies to the
two languages, the test gives the same condition to the Python adapter and to the
TypeScript adapter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import (
    check,
    config,
    extract,
    extraction,
    facts_file,
    file_write,
    history,
    python_syntax,
    repo_files,
    unknown_causes,
)
from systemap.cli import main
from systemap.model import Component, Model, Region

PY_TREE = {
    "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
}
TS_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
}
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
LINKS = pytest.mark.skipif(sys.platform == "win32", reason="the test makes symbolic links")


def facts_of(root: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(root, tree)
    return extract.build(config.load(root))


def _model(component: Component) -> Model:
    return Model(
        canvas=(0, 0),
        containers=(),
        regions=(Region(id="core", label="CORE", box=(0, 0, 0, 0)),),
        components=(component,),
        flows=(),
        flow_kinds=(),
    )


def _card(module: str, entry: str) -> Component:
    return Component("Api", "Gives a name.", implemented_by=(module,), entry=entry, region="core")


def _names(record: dict[str, Any]) -> set[str]:
    return {str(entry["name"]) for entry in record.get("names", [])}


# ---- py-adapter-1: a parent folder that changes to a link ---------------------------


def _swap_to_link(folder: Path, outside: Path) -> None:
    """Move the folder away, and put a link to the outside folder at its path."""
    folder.rename(folder.with_name(folder.name + "-old"))
    folder.symlink_to(outside, target_is_directory=True)


@pytest.fixture
def swap(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    root, outside = tmp_path / "repo", tmp_path / "outside"
    (root / "safe").mkdir(parents=True)
    outside.mkdir()
    (root / "safe" / "data.txt").write_text("inside\n", encoding="utf-8")
    (outside / "data.txt").write_text("secret\n", encoding="utf-8")
    yield root, outside


@LINKS
def test_a_parent_folder_that_changes_after_the_check_does_not_give_an_outside_read(
    swap: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance: the folder `safe` changes to a link out of the repository after
    `checked` and before the open. `read_text` and `read_bytes` give `RepoPathError` in 2
    of 2 reads, and neither gives the outside text. Without the change, the read gives
    the inside text."""
    root, outside = swap
    assert repo_files.read_text(root, "safe/data.txt") == "inside\n"
    real = repo_files.checked

    def checked_then_swapped(base: Path, rel: str | os.PathLike[str]) -> Path:
        found = real(base, rel)  # type: ignore[arg-type]
        if not (root / "safe").is_symlink():
            _swap_to_link(root / "safe", outside)
        return found

    monkeypatch.setattr(repo_files, "checked", checked_then_swapped)
    with pytest.raises(repo_files.RepoPathError):
        repo_files.read_text(root, "safe/data.txt")
    with pytest.raises(repo_files.RepoPathError):
        repo_files.read_bytes(root, "safe/data.txt")


@LINKS
def test_a_parent_folder_that_changes_after_the_check_does_not_give_an_outside_write(
    swap: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance: the folder `safe` changes to a link out of the repository after the
    folder check of `write_atomic` and of `locked`. Each gives `RefusedFile`, and the
    outside folder gets no new file (0 of 2 writes go out)."""
    root, outside = swap
    real = file_write.folder

    def folder_then_swapped(base: Path, path: Path) -> None:
        real(base, path)
        if not (root / "safe").is_symlink():
            _swap_to_link(root / "safe", outside)

    monkeypatch.setattr(file_write, "folder", folder_then_swapped)
    with pytest.raises(file_write.RefusedFile):
        file_write.write_atomic(root, root / "safe" / "out.txt", "text\n")
    assert sorted(p.name for p in outside.iterdir()) == ["data.txt"]
    (root / "safe").unlink()
    (root / "safe-old").rename(root / "safe")
    with pytest.raises(file_write.RefusedFile), file_write.locked(root, root / "safe" / "out"):
        pass
    assert sorted(p.name for p in outside.iterdir()) == ["data.txt"]


@LINKS
@pytest.mark.skipif(not repo_files.WALK, reason="the platform cannot open relative to a folder")
def test_a_folder_that_changes_just_before_the_walk_is_refused(
    swap: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance: the folder `safe` changes to a link out of the repository after the
    resolution and before the walk of `repo_files.open_folder`. A read, a write, and a
    lock each give a refusal, and the outside folder gets no new file."""
    root, outside = swap
    real = repo_files.open_folder

    def swapped_then_opened(base: Path, parts: Any, make: bool = False) -> int:
        if not (root / "safe").is_symlink():
            _swap_to_link(root / "safe", outside)
        return real(base, parts, make)

    monkeypatch.setattr(repo_files, "open_folder", swapped_then_opened)
    with pytest.raises(repo_files.RepoPathError, match="is a link"):
        repo_files.read_text(root, "safe/data.txt")
    for step in (
        lambda: file_write.write_atomic(root, root / "safe" / "out.txt", "text\n"),
        lambda: file_write.locked(root, root / "safe" / "out").__enter__(),
    ):
        (root / "safe").unlink()
        (root / "safe-old").rename(root / "safe")
        with pytest.raises(file_write.RefusedFile, match="is a link"):
            step()
    assert sorted(p.name for p in outside.iterdir()) == ["data.txt"]


@LINKS
def test_a_link_in_the_repository_is_still_followed(tmp_path: Path) -> None:
    """Acceptance: a folder link to a folder in the repository still gives the file for
    a read and for a write, as before the repair."""
    root = tmp_path / "repo"
    (root / "real").mkdir(parents=True)
    (root / "real" / "data.txt").write_text("inside\n", encoding="utf-8")
    (root / "alias").symlink_to(root / "real", target_is_directory=True)
    assert repo_files.read_text(root, "alias/data.txt") == "inside\n"
    file_write.write_atomic(root, root / "alias" / "deep" / "out.txt", "text\n")
    assert (root / "real" / "deep" / "out.txt").read_text(encoding="utf-8") == "text\n"
    assert file_write.read_text(root, root / "alias" / "deep" / "out.txt") == "text\n"
    with file_write.locked(root, root / "alias" / "deep" / "out"):
        pass
    assert (root / "real" / "deep" / "out.lock").is_file()


# ---- py-adapter-2: an unreadable re-export surface is not known ---------------------


def test_a_star_reexport_from_a_module_that_did_not_parse_is_not_known(tmp_path: Path) -> None:
    """Acceptance: in 2 of 2 languages, a `*` re-export from a module that did not parse
    gives one unknown record with the cause `reexport`. A component that claims only the
    package, with `entry="serve"`, gives no entry line and no interface line. A component
    with an entry that a parsed surface does not define still gives the entry line."""
    py = facts_of(
        tmp_path / "py",
        {
            **PY_TREE,
            "pkg/__init__.py": "from .service import *\n",
            "pkg/service.py": "def serve() -> None:\n    pass\n\n)\n",
        },
    )
    ts = facts_of(
        tmp_path / "ts",
        {
            **TS_TREE,
            "src/index.ts": 'export * from "./service";\n',
            "src/service.ts": "export function serve(): void {\n  return;\n}\n}}\n",
        },
    )
    for facts, module, target in ((py, "pkg", "pkg.service"), (ts, "web.index", "web.service")):
        record = facts["components"][module]
        assert facts["components"][target]["completeness"]["parsed"] is False
        causes = [unknown_causes.of(item) for item in record.get("unknown", [])]
        assert causes.count(unknown_causes.REEXPORT) == 1, module
        card = Component(
            "Api",
            "Gives a name.",
            implemented_by=(module,),
            entry="serve",
            interface="serve()",
            region="core",
        )
        assert check.check_entry(_model(card), facts) == [], module
        assert check.check_interface(_model(card), facts) == [], module
    parsed = facts_of(tmp_path / "py2", {**PY_TREE, "pkg/__init__.py": "def other(): ...\n"})
    assert check.check_entry(_model(_card("pkg", "serve")), parsed) == [
        "Api has entry serve, but its modules do not define this entry (pkg)."
    ]


# ---- py-adapter-3 and py-adapter-4: `__all__` limits a `*` re-export ---------------


def test_an_empty_all_list_gives_no_star_names(tmp_path: Path) -> None:
    """Acceptance: `__all__ = []` in `pkg/service.py` gives `star_export` false on
    `serve`, and the package that imports `*` from it has no name `serve`. A module
    without `__all__` still gives `serve`."""
    facts = facts_of(
        tmp_path,
        {
            **PY_TREE,
            "pkg/__init__.py": "from .service import *\nfrom .open import *\n",
            "pkg/service.py": "__all__ = []\n\n\ndef serve() -> None:\n    pass\n",
            "pkg/open.py": "def run() -> None:\n    pass\n",
        },
    )
    components = facts["components"]
    serve = [e for e in components["pkg.service"]["names"] if e["name"] == "serve"]
    assert serve[0]["star_export"] is False
    assert _names(components["pkg"]) == {"run"}


def test_the_all_list_of_a_package_limits_the_names_of_its_star_reexports(
    tmp_path: Path,
) -> None:
    """Acceptance: `pkg.mid` imports `first` and `second` through `*` and sets
    `__all__ = ["first"]`. The root package that imports `*` from `pkg.mid` has the names
    {first}, not {first, second}. `pkg.mid` keeps both names, and `second` has
    `star_export` false. A computed `__all__` in `pkg.mid` gives the root package one
    unknown record with the cause `reexport`."""
    tree = {
        **PY_TREE,
        "pkg/__init__.py": "from .mid import *\n",
        "pkg/mid/__init__.py": 'from .a import *\n\n__all__ = ["first"]\n',
        "pkg/mid/a.py": "def first() -> None:\n    pass\n\n\ndef second() -> None:\n    pass\n",
    }
    components = facts_of(tmp_path / "literal", tree)["components"]
    assert _names(components["pkg"]) == {"first"}
    assert _names(components["pkg.mid"]) == {"first", "second"}
    second = [e for e in components["pkg.mid"]["names"] if e["name"] == "second"]
    assert second[0]["star_export"] is False
    computed = {**tree, "pkg/mid/__init__.py": "from .a import *\n\n__all__ = list(['first'])\n"}
    root = facts_of(tmp_path / "computed", computed)["components"]["pkg"]
    causes = [unknown_causes.of(item) for item in root.get("unknown", [])]
    assert causes == [unknown_causes.REEXPORT]


# ---- py-adapter-5: import bindings in different scopes ------------------------------


def test_imports_of_one_name_in_two_functions_keep_two_call_sites(tmp_path: Path) -> None:
    """Acceptance: `first` imports `save` from `pkg.a`, and `second` imports `save` from
    `pkg.b`. `call_sites` has one record for each target, each with the use in its own
    function. A function import of `save` hides a module import of `save` in that
    function: the module binding gets only the use outside the function."""
    facts = facts_of(
        tmp_path,
        {
            **PY_TREE,
            "pkg/a.py": "def save() -> None:\n    pass\n",
            "pkg/b.py": "def save() -> None:\n    pass\n",
            "pkg/user.py": (
                "def first() -> None:\n"  # 1
                "    from pkg.a import save\n"  # 2
                "    save()\n"  # 3
                "\n\n"
                "def second() -> None:\n"  # 6
                "    from pkg.b import save\n"  # 7
                "    save()\n"  # 8
            ),
            "pkg/shadow.py": (
                "from pkg.a import save\n"  # 1
                "\n\n"
                "def other() -> None:\n"  # 4
                "    from pkg.b import save\n"  # 5
                "    save()\n"  # 6
                "\n\n"
                "save()\n"  # 9
            ),
        },
    )
    sites = facts["components"]["pkg.user"]["call_sites"]
    found = {(s["target"], s["name"]): s["uses"] for s in sites}
    assert found == {("pkg.a", "save"): [[3, 1, ""]], ("pkg.b", "save"): [[8, 6, ""]]}
    shadow = facts["components"]["pkg.shadow"]["call_sites"]
    found = {(s["target"], s["name"]): s["uses"] for s in shadow}
    assert found == {("pkg.a", "save"): [[9, 0, ""]], ("pkg.b", "save"): [[6, 4, ""]]}


# ---- py-adapter-6: an absent import target is not its ancestor ----------------------


def test_an_absent_import_target_does_not_become_its_package(tmp_path: Path) -> None:
    """Acceptance: `from pkg.optional import plugin` and `import pkg.extra` with no
    `pkg.optional` and no `pkg.extra` module give no `uses` record for `pkg`. The two
    imports are in `unresolved_imports`. An import of a name from a present module still
    gives a `uses` record."""
    facts = facts_of(
        tmp_path,
        {
            **PY_TREE,
            "pkg/__init__.py": "VERSION = 1\n",
            "pkg/user.py": (
                "try:\n    from pkg.optional import plugin\nexcept ImportError:\n"
                "    plugin = None\n\nimport pkg.extra\nfrom pkg import VERSION\n"
            ),
            "pkg/other.py": "import pkg.extra\n",
        },
    )
    user = facts["components"]["pkg.user"]
    assert user["uses"] == {"pkg": ["VERSION"]}
    assert facts["components"]["pkg.other"]["uses"] == {}
    assert user["completeness"]["unresolved_imports"] == ["pkg.extra", "pkg.optional"]


# ---- py-adapter-7: a relative import in a test file ---------------------------------


def test_a_relative_import_in_a_test_file_refers_to_the_module(tmp_path: Path) -> None:
    """Acceptance: in 2 of 2 languages, a test file in the package with a relative import
    of the reader module gives the reader module one test reference."""
    py = facts_of(
        tmp_path / "py",
        {
            "systemap.toml": '[package_roots]\n"src/pkg" = "pkg"\n',
            "src/pkg/__init__.py": "",
            "src/pkg/reader.py": "def read() -> None:\n    pass\n",
            "src/pkg/tests/__init__.py": "",
            "src/pkg/tests/test_reader.py": (
                "from ..reader import read\n\n\ndef test_read() -> None:\n    read()\n"
            ),
        },
    )
    assert py["components"]["pkg.reader"]["tests"] == ["src/pkg/tests/test_reader.py::test_read"]
    ts = facts_of(
        tmp_path / "ts",
        {
            **TS_TREE,
            "src/reader.ts": "export function read(): void {}\n",
            "tests/reader.spec.ts": (
                'import { read } from "../src/reader";\ntest("reads", () => read());\n'
            ),
        },
    )
    assert ts["components"]["web.reader"]["tests"] == ["tests/reader.spec.ts::reads"]


# ---- py-adapter-8: a `__main__` module and a console script -------------------------


def _main_module(facts: dict[str, Any]) -> dict[str, str]:
    return next(p for p in facts["entry_points"] if p["kind"] == "main_module")


def test_a_main_module_that_does_not_start_the_function_is_a_separate_entry(
    tmp_path: Path,
) -> None:
    """Acceptance: a `__main__` module that calls the console script function only in a
    helper function, and does a different top-level operation, has an empty `same_as`.
    A `__main__` module that calls the function at the top level has `same_as` set to the
    console script."""
    tree = {
        **PY_TREE,
        "pyproject.toml": '[project]\nname = "pkg"\n[project.scripts]\npkg = "pkg.cli:main"\n',
        "pkg/cli.py": "def main() -> None:\n    pass\n",
        "pkg/__main__.py": (
            'from pkg.cli import main\n\n\ndef helper() -> None:\n    main()\n\n\nprint("other")\n'
        ),
    }
    assert _main_module(facts_of(tmp_path / "helper", tree))["same_as"] == ""
    started = {**tree, "pkg/__main__.py": "from pkg.cli import main\n\nmain()\n"}
    assert _main_module(facts_of(tmp_path / "started", started))["same_as"] != ""


# ---- py-adapter-9: an annotation that the module evaluates --------------------------


def test_an_evaluated_annotation_call_is_code() -> None:
    """Acceptance: `__version__: print("start") = "1"` holds code. With postponed
    annotations it holds no code. `__version__: str = "1"` holds no code."""
    assert python_syntax.holds_no_code('__version__: print("start") = "1"\n') is False
    postponed = 'from __future__ import annotations\n\n__version__: print("start") = "1"\n'
    assert python_syntax.holds_no_code(postponed) is True
    assert python_syntax.holds_no_code('__version__: str = "1"\n') is True


# ---- py-adapter-10: a link loop -----------------------------------------------------


@LINKS
def test_a_link_loop_is_a_module_that_could_not_be_read(tmp_path: Path) -> None:
    """Acceptance: a Python source file that is a link to itself does not stop extraction.
    Its module record has `parsed` false and the cause `read`. `systemap init` and
    `systemap extract` exit 0. `repo_files.checked` gives `RepoPathError` for the link."""
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/reader.py": "def read() -> None: ...\n"})
    write_tree(tmp_path, {"pkg/writer.py": "def write() -> None: ...\n"})
    (tmp_path / "pkg" / "loop.py").symlink_to("loop.py")
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    state = extract.build(config.load(tmp_path))["components"]["pkg.loop"]["completeness"]
    assert state["parsed"] is False
    assert state["cause"] == unknown_causes.READ
    with pytest.raises(repo_files.RepoPathError, match="link loop"):
        repo_files.checked(tmp_path, "pkg/loop.py")


@LINKS
@pytest.mark.xfail(
    raises=RuntimeError,
    strict=True,
    reason="typescript_projects.config_for resolves the link before the shared read. The "
    "TypeScript workstream owns that module.",
)
def test_a_typescript_link_loop_is_a_module_that_could_not_be_read(tmp_path: Path) -> None:
    """Acceptance: the TypeScript version of the test above. A `.ts` file that is a link
    to itself gives a module record with `parsed` false and the cause `read`."""
    write_tree(tmp_path, {**TS_TREE, "src/tools.ts": "export function run(): void {}\n"})
    (tmp_path / "src" / "loop.ts").symlink_to("loop.ts")
    state = extract.build(config.load(tmp_path))["components"]["web.loop"]["completeness"]
    assert state["parsed"] is False
    assert state["cause"] == unknown_causes.READ


# ---- py-adapter-11: a facts file that is not UTF-8 ----------------------------------


def test_a_facts_file_that_is_not_utf8_is_not_usable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: a facts file with an invalid UTF-8 byte gives an empty table, as a
    facts file that is not JSON does. `systemap facts` exits 1 with the line "No facts
    are available" and the correction `run: systemap extract`. `systemap extract` exits
    0 and writes facts that `read_facts` can read."""
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/reader.py": "def read() -> None: ...\n"})
    write_tree(tmp_path, {"pkg/writer.py": "def write() -> None: ...\n"})
    init_two_cards(tmp_path, "--no-ci")
    path = tmp_path / "docs" / "map" / "map.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"version": "\xff"}\n')
    assert facts_file.read_facts(path, tmp_path) == {}
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "facts"]) == 1
    out = capsys.readouterr().out
    assert "No facts are available at docs/map/map.json" in out
    assert "run: systemap extract" in out
    assert main(["--root", str(tmp_path), "extract"]) == 0
    assert facts_file.read_facts(path, tmp_path)["components"]


# ---- py-adapter-12: a history cache record that is not a facts table ----------------


def test_a_history_cache_record_that_is_not_a_facts_table_is_extracted_again(
    tmp_path: Path,
) -> None:
    """Acceptance: a cache file with the JSON value `[]` gives a facts table with
    `components` from `facts_at`, and the cache file then holds that table."""
    write_tree(tmp_path, {**PY_TREE, "pkg/tools.py": "def run() -> None:\n    pass\n"})
    subprocess.run([*GIT, "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run([*GIT, "commit", "-qm", "base"], cwd=tmp_path, check=True)
    sha = subprocess.run(
        [*GIT, "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()
    cfg = config.load(tmp_path)
    first = history.facts_at(cfg, sha)
    (cached,) = list(history.cache_dir(cfg).glob(f"{sha}-*.json"))
    for value in ("[]", '{"components": []}'):
        cached.write_text(value, encoding="utf-8")
        again = history.facts_at(cfg, sha)
        assert isinstance(again, dict)
        assert again["components"] == first["components"]
        assert '"components"' in cached.read_text(encoding="utf-8")


# ---- py-adapter-13: a changed specification section ---------------------------------


def test_a_changed_specification_section_makes_the_facts_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: after a heading change in the `spec_path` file, `drift` gives the line
    "specification sections changed since the map was built", and `systemap extract
    --check` exits 1. Without the change, `drift` gives no line."""
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/tools.py": "def run() -> None:\n    pass\n",
            "SPEC.md": "# Spec\n\n## First\n",
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    settings = tmp_path / "systemap.toml"
    settings.write_text(
        'spec_path = "SPEC.md"\n' + settings.read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert main(["--root", str(tmp_path), "extract"]) == 0
    cfg = config.load(tmp_path)
    stored = facts_file.read_facts(cfg.facts_path, cfg.root)
    assert stored["spec_sections"] == [{"level": "2", "title": "First"}]
    assert extraction.drift(extraction.build(cfg), stored) == []
    (tmp_path / "SPEC.md").write_text("# Spec\n\n## Second\n", encoding="utf-8")
    assert extraction.drift(extraction.build(cfg), stored) == [
        "specification sections changed since the map was built"
    ]
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "extract", "--check"]) == 1
    assert "specification sections changed" in capsys.readouterr().out


# ---- py-adapter-14: a folder with the name `__init__` -------------------------------


def test_a_folder_named_init_keeps_its_module_name_part(tmp_path: Path) -> None:
    """Acceptance: `pkg/__init__/tools.py` has the module `pkg.__init__.tools`, and
    `pkg/tools.py` has `pkg.tools`. Extraction gives no duplicate-module error. The package
    file `pkg/__init__.py` still has the module `pkg`."""
    facts = facts_of(
        tmp_path,
        {
            **PY_TREE,
            "pkg/__init__/tools.py": "def first() -> None:\n    pass\n",
            "pkg/tools.py": "def second() -> None:\n    pass\n",
        },
    )
    assert {"pkg", "pkg.tools", "pkg.__init__.tools"} <= set(facts["components"])
    assert facts["components"]["pkg"]["file"] == "pkg/__init__.py"
