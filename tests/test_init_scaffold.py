"""The files that `systemap init` writes, read back by the configuration reader.

Each test runs `init` on a small fixture tree and reads the written files with the
same reader that the other commands use.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, judgement, python_repo, scaffold
from systemap.cli import main
from systemap.model import Component, Model

STARTER = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
}

# A TypeScript workspace: each package has its own tsconfig.json, the root has none.
WORKSPACE = {
    "package.json": '{"name": "mono", "private": true, "workspaces": ["packages/*"]}\n',
    "packages/web/tsconfig.json": '{"compilerOptions": {"strict": true}}\n',
    "packages/web/src/index.ts": "export function start(): void {}\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def toml(root: Path) -> dict[str, object]:
    with (root / "systemap.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_init_writes_model_and_out_dir_as_top_level_settings(tmp_path: Path) -> None:
    write_tree(tmp_path, STARTER)
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    data = toml(tmp_path)
    assert data["package_roots"] == {"pkg": "pkg"}
    assert data["model"] == "map/model.py"
    assert data["out_dir"] == "docs/map"
    # The two settings have an effect: a moved model and output directory are used.
    text = (tmp_path / "systemap.toml").read_text(encoding="utf-8")
    text = text.replace('model = "map/model.py"', 'model = "maps/model.py"')
    text = text.replace('out_dir = "docs/map"', 'out_dir = "site/map"')
    (tmp_path / "systemap.toml").write_text(text, encoding="utf-8")
    (tmp_path / "maps").mkdir()
    (tmp_path / "map/model.py").rename(tmp_path / "maps/model.py")
    cfg = config.load(tmp_path)
    assert (cfg.model, cfg.out_dir) == ("maps/model.py", "site/map")
    assert cfg.package_roots == (("pkg", "pkg"),)


# The table that an earlier init wrote: the two settings are in [package_roots].
EARLIER_TABLE = '[package_roots]\n"pkg" = "pkg"\nmodel = "map/model.py"\nout_dir = "docs/map"\n'


def test_a_default_setting_inside_package_roots_is_not_a_package_root(tmp_path: Path) -> None:
    write_tree(tmp_path, {**STARTER, "systemap.toml": EARLIER_TABLE})
    assert config.load(tmp_path).package_roots == (("pkg", "pkg"),)
    # A top-level directory named model does not become a package root.
    (tmp_path / "model").mkdir()
    (tmp_path / "model/train.py").write_text("STEPS = 1\n", encoding="utf-8")
    cfg = config.load(tmp_path)
    assert cfg.package_roots == (("pkg", "pkg"),)
    assert (cfg.model, cfg.out_dir) == ("map/model.py", "docs/map")


def test_a_changed_setting_inside_package_roots_is_a_configuration_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    table = EARLIER_TABLE.replace('"map/model.py"', '"maps/model.py"')
    write_tree(tmp_path, {**STARTER, "systemap.toml": table})
    assert run("--root", str(tmp_path), "extract") == 2
    err = capsys.readouterr().err
    assert "[package_roots] contains the key model" in err
    assert "Move the model line above the [package_roots] line." in err
    # A directory named model does not hide the problem: the import name is a path.
    (tmp_path / "model").mkdir()
    assert run("--root", str(tmp_path), "extract") == 2
    assert "[package_roots] contains the key model" in capsys.readouterr().err


def test_a_configured_package_root_that_is_missing_is_a_configuration_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {**STARTER, "systemap.toml": '[package_roots]\n"src/pkg" = "pkg"\n'})
    assert run("--root", str(tmp_path), "extract") == 2
    err = capsys.readouterr().err
    assert "The package root src/pkg is not a directory." in err
    assert "Traceback" not in err


def test_the_answer_example_in_the_configuration_is_a_judgement_line(tmp_path: Path) -> None:
    write_tree(tmp_path, STARTER)
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    text = (tmp_path / "systemap.toml").read_text(encoding="utf-8")
    example = next(line for line in text.splitlines() if line.startswith("# answered = "))
    found = re.search(r'item = "([^"]+)"', example)
    assert found is not None
    reader = Component(id="Reader", does="Reads.", implemented_by=("pkg.reader",))
    model = Model(
        canvas=(100, 100), containers=(), regions=(), components=(reader,), flows=(), flow_kinds=()
    )
    printed = judgement.single_module(model, {})
    assert printed == [found.group(1)]
    # An exact answer is pending without its evidence digest, so the example has one.
    assert "evidence = " in example


@pytest.mark.parametrize("name", ['we"ird', "back\\slash", "tab\there"])
def test_init_writes_a_project_name_that_the_readers_accept(tmp_path: Path, name: str) -> None:
    write_tree(tmp_path, STARTER)
    assert run("--root", str(tmp_path), "init", "--no-ci", "--name", name) == 0
    cfg = config.load(tmp_path)
    assert cfg.name == name
    model, _meaning = config.load_model(cfg.model_path)
    assert model.containers[0].label == name.upper()


def test_init_selects_typescript_for_a_workspace_without_a_root_tsconfig(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, WORKSPACE)
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    out = capsys.readouterr().out
    text = (tmp_path / "systemap.toml").read_text(encoding="utf-8")
    assert toml(tmp_path)["language"] == "typescript"
    assert "package_roots" not in toml(tmp_path)
    assert "Python packages" not in text
    # No pyproject.toml: the note about Python tool settings does not apply.
    assert "deptry" not in out and "pyproject.toml" not in out
    assert run("--root", str(tmp_path), "extract") == 2
    err = capsys.readouterr().err
    assert '("path" = "module name")' in err
    assert "__init__.py" not in err


def test_init_finds_a_package_with_the_name_of_an_output_directory(tmp_path: Path) -> None:
    # The pypa/build layout: the package itself has the name build.
    write_tree(
        tmp_path,
        {
            "src/build/__init__.py": "",
            "src/build/main.py": "def run() -> None:\n    pass\n",
            # Build output has no __init__.py in build/, and tests and docs stay out.
            "build/lib/other/__init__.py": "",
            "tests/__init__.py": "",
            "docs/__init__.py": "",
        },
    )
    assert python_repo.discover_roots(tmp_path) == [("src/build", "build")]
    candidates = python_repo.candidate_packages(tmp_path)
    assert "src/build" in candidates and "build/lib/other" not in candidates
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    assert toml(tmp_path)["package_roots"] == {"src/build": "build"}


def test_a_dependency_directory_does_not_select_typescript(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {"node_modules/tool/tsconfig.json": "{}\n", "app/main.py": "print(1)\n"},
    )
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    assert toml(tmp_path)["language"] == "python"


def test_the_python_tool_note_stays_for_python(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, STARTER)
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    assert "\n".join(scaffold.TOOLING_NOTE) + "\nNext," in capsys.readouterr().out
