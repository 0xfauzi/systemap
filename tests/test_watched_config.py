"""`systemap live` watches the configuration files that the language adapters give.

Before this change, `serve.CONFIG_FILES` named `package.json` and `tsconfig.json` in
shared code. Thus a Python repository with a `package.json` file rendered again after
each edit of that file, although extraction does not read it. A new adapter also had to
change `serve.py`.

Acceptance: a Python repository watches `systemap.toml`, `pyproject.toml`, and no
TypeScript file. A TypeScript repository watches `package.json` and `tsconfig.json`. If
the configuration does not load, the command watches the files of each adapter.
"""

from __future__ import annotations

from pathlib import Path

from conftest import TINY_PACKAGE, write_tree

from systemap import language as languages
from systemap import serve

CONFIG_NAMES = {"systemap.toml", "pyproject.toml", "package.json", "tsconfig.json"}


def _config_names(root: Path) -> set[str]:
    found = {p.relative_to(root).as_posix() for p in serve.watched(root)}
    return found & CONFIG_NAMES


def test_a_python_repository_watches_the_python_configuration(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {**TINY_PACKAGE, "pyproject.toml": '[project]\nname = "pkg"\n', "package.json": "{}"},
    )
    assert _config_names(tmp_path) == {"systemap.toml", "pyproject.toml"}


def test_a_typescript_repository_watches_the_typescript_configuration(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "src/index.ts": "export const one = 1;\n",
        },
    )
    expected = {"systemap.toml", "pyproject.toml"} | set(
        languages.repository("typescript").config_files
    )
    assert _config_names(tmp_path) == expected == CONFIG_NAMES


def test_without_a_configuration_each_adapter_file_is_watched(tmp_path: Path) -> None:
    write_tree(tmp_path, {"systemap.toml": "language = 3\n"})
    every = {name for n in languages.names() for name in languages.repository(n).config_files}
    assert _config_names(tmp_path) == {"systemap.toml", "pyproject.toml"} | every
