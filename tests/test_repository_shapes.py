"""Hostile repository input gives a ConfigError or a record. It does not give a traceback.

Findings g1ts-3, rest-4, g1ts-10, and rest-6 of the audit. Before the change:

- `project = "oops"` or a Poetry script `x = 1` in pyproject.toml gave AttributeError.
- An absolute uv workspace member pattern gave NotImplementedError.
- A `..` member, a linked member, and a top-level link to a package out of the
  repository put the outside names in the facts.
- A tsconfig.json include entry that names a link to a folder out of the repository
  became the TypeScript package root.
- A folder tree with 1000 levels gave RecursionError in `os.walk`.

Each test below failed before the change.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, python_entry, python_repo, tree_walk
from systemap.typescript_roots import discover_typescript_roots

PACKAGE = {"app/__init__.py": "X = 1\n"}


def _repo(tmp_path: Path, pyproject: str) -> Path:
    root = tmp_path / "repo"
    write_tree(root, {**PACKAGE, "pyproject.toml": pyproject})
    return root


def _outside(tmp_path: Path) -> Path:
    project = tmp_path / "outside" / "victimproj"
    write_tree(project, {"victimpkg/__init__.py": "X = 1\n", "pyproject.toml": ""})
    return project


def test_a_project_value_that_is_not_a_table_is_a_config_error(tmp_path: Path) -> None:
    root = _repo(tmp_path, 'project = "oops"\n')
    with pytest.raises(config.ConfigError, match="the value of project must be a table"):
        python_entry.console_scripts(root)
    with pytest.raises(config.ConfigError, match="the value of project must be a table"):
        python_repo.PYTHON_REPOSITORY.project_name(root)


def test_a_poetry_script_that_is_not_a_string_or_a_table_is_a_config_error() -> None:
    data = {"tool": {"poetry": {"scripts": {"x": 1}}}}
    with pytest.raises(config.ConfigError, match=r"tool\.poetry\.scripts\.x must be a string"):
        python_entry.in_pyproject(data, {})
    with pytest.raises(config.ConfigError, match=r"tool\.poetry\.scripts must be a table"):
        python_entry.in_pyproject({"tool": {"poetry": {"scripts": "x"}}}, {})


def test_an_absolute_workspace_member_pattern_is_a_config_error(tmp_path: Path) -> None:
    outside = _outside(tmp_path)
    root = _repo(tmp_path, f'[tool.uv.workspace]\nmembers = ["{outside.parent}/*"]\n')
    with pytest.raises(config.ConfigError, match="must be a relative path"):
        python_repo.discover_roots(root)


def test_a_parent_workspace_member_pattern_is_a_config_error(tmp_path: Path) -> None:
    _outside(tmp_path)
    root = _repo(tmp_path, '[tool.uv.workspace]\nmembers = ["../outside/victimproj"]\n')
    with pytest.raises(config.ConfigError, match="must be a relative path"):
        python_repo.discover_roots(root)


def test_a_workspace_members_value_that_is_not_an_array_is_a_config_error(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path, '[tool.uv.workspace]\nmembers = "pkgs/*"\n')
    with pytest.raises(config.ConfigError, match="must be an array"):
        python_repo.workspace_members(root)


def test_a_linked_workspace_member_out_of_the_root_gives_no_root(tmp_path: Path) -> None:
    outside = _outside(tmp_path)
    root = _repo(tmp_path, '[tool.uv.workspace]\nmembers = ["linked", "pkgs/*"]\n')
    (root / "linked").symlink_to(outside)
    write_tree(root, {"pkgs/one/one/__init__.py": "X = 1\n"})
    assert python_repo.workspace_members(root) == [root / "pkgs" / "one"]
    assert python_repo.discover_roots(root) == [("app", "app"), ("pkgs/one/one", "one")]


def test_a_top_level_link_to_an_outside_package_is_not_a_root(tmp_path: Path) -> None:
    outside = _outside(tmp_path)
    root = _repo(tmp_path, '[project]\nname = "fx"\n')
    (root / "victimpkg").symlink_to(outside / "victimpkg")
    assert python_repo.discover_roots(root) == [("app", "app")]


def test_a_linked_typescript_include_folder_is_not_the_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write_tree(outside, {"victim.ts": "export const victim = 1;\n"})
    root = tmp_path / "repo"
    write_tree(
        root,
        {
            "package.json": '{"name": "fx"}\n',
            "tsconfig.json": '{"include": ["lib/**/*"]}\n',
            "src/a.ts": "export const a = 1;\n",
        },
    )
    (root / "lib").symlink_to(outside)
    assert discover_typescript_roots(root) == [("src", "fx")]


def _deep(root: Path, levels: int) -> Path:
    folder = root
    for _ in range(levels):
        folder = folder / "d"
        folder.mkdir(parents=True)
    return folder


def test_a_very_deep_tree_is_a_config_error_that_names_the_folder(tmp_path: Path) -> None:
    # Before the change, os.walk gave RecursionError at about 985 levels.
    root = tmp_path / "repo"
    _deep(root, 1000)
    with pytest.raises(config.ConfigError, match="levels below") as caught:
        list(tree_walk.walk(root))
    assert str(root / ("d/" * tree_walk.MAX_DEPTH).rstrip("/")) in str(caught.value)
    with pytest.raises(config.ConfigError):
        config.walk(root, python_repo.package_dir)
    with pytest.raises(config.ConfigError):
        list(python_repo.python_paths(root))


def test_a_walk_that_stops_above_the_limit_gives_no_error(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _deep(root, tree_walk.MAX_DEPTH + 5)
    assert len(config.walk(root, python_repo.package_dir, depth=3)) == 3


def test_the_walk_gives_the_steps_of_os_walk(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    write_tree(root, {"b/x.py": "", "a/c/y.py": "", "a/z.txt": "", ".h/k.py": "", "top.py": ""})
    (root / "link").symlink_to(root / "a")
    (root / "loose").symlink_to(root / "top.py")

    def steps(walker: Iterable[tree_walk.Step]) -> list[tree_walk.Step]:
        out = []
        for here, names, files in walker:
            names[:] = sorted(name for name in names if name != ".h")
            out.append((here, list(names), sorted(files)))
        return out

    assert list(tree_walk.walk(root)) == list(os.walk(root))
    assert steps(tree_walk.walk(root)) == steps(os.walk(root))
