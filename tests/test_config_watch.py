"""The live watcher watches each configuration file that the language adapter reads
(result `followup-extends`).

Before this change, the watcher watched only the configuration names of the adapter
(`tsconfig.json` and `package.json`). A tsconfig `extends` target with a different name,
such as `tsconfig.base.json`, and a `references` target were not watched. Thus a change
to such a file did not refresh the page.

Acceptance, written before the change:

- TypeScript: the watched files include an `extends` target with a different name, an
  `extends` target in node_modules, a `references` target, and the `extends` targets of
  a `references` target. After a change to `tsconfig.base.json`, the scan requests one
  render.
- A tsconfig file that is not valid JSON, and an `extends` cycle, do not stop the
  watcher. The watcher watches the file that is not valid.
- Python: the watched files include `systemap.toml`, `pyproject.toml`, and a
  `pyproject.toml` file between the repository root and a package root. After a change
  to `pyproject.toml`, the scan requests one render.
- For each language, the configuration files in the watched list are the systemap
  configuration files and the files that the adapter call `config_paths` gives. The
  watcher gets no other configuration file.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from conftest import write_tree

from systemap import config, live_watch
from systemap import language as languages

TYPESCRIPT_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name": "web"}\n',
    "tsconfig.json": (
        '{\n  // the base settings\n  "extends": "./tsconfig.base",\n'
        '  "references": [{"path": "./packages/lib"}, {"path": "./tsconfig.build.json"}],\n}\n'
    ),
    "tsconfig.base.json": '{"extends": ["@scope/tsconfig/strict.json"]}\n',
    "node_modules/@scope/tsconfig/strict.json": '{"compilerOptions": {"strict": true}}\n',
    "tsconfig.build.json": '{"compilerOptions": {}}\n',
    "packages/lib/tsconfig.json": '{"extends": "../../config/tsconfig.shared.json"}\n',
    "config/tsconfig.shared.json": '{"compilerOptions": {}}\n',
    "other/tsconfig.unused.json": "{}\n",
    "src/index.ts": "export const one = 1;\n",
}
PYTHON_TREE = {
    "systemap.toml": 'language = "python"\n[package_roots]\n"libs/core/src/core" = "core"\n',
    "pyproject.toml": '[project]\nname = "all"\n',
    "libs/core/pyproject.toml": '[project]\nname = "core"\n',
    "libs/core/src/core/__init__.py": "",
    "other/pyproject.toml": '[project]\nname = "other"\n',
}


def _names(root: Path) -> set[str]:
    return {
        p.relative_to(root).as_posix() for p in live_watch.watched(root) if p.is_relative_to(root)
    }


def _configs(root: Path, language: str) -> set[str]:
    """Give the watched files that are not source, test, or model files."""
    suffixes = languages.repository(language).source_suffixes
    return {name for name in _names(root) if not name.endswith(suffixes)}


def _adapter_paths(root: Path, language: str, folders: list[str]) -> set[str]:
    adapter = languages.repository(language)
    paths = adapter.config_paths(root, [root / folder for folder in folders])
    return {p.relative_to(root).as_posix() for p in paths}


class _Requests:
    count = 0

    def request(self) -> None:
        self.count += 1


class _Ticks:
    """The stop event of the scan, without a clock. Each wait() does the next action."""

    def __init__(self, *actions: Callable[[], None]) -> None:
        self.actions = list(actions)

    def wait(self, _seconds: float) -> bool:
        if not self.actions:
            return True
        self.actions.pop(0)()
        return False


def _requests_after_edit(root: Path, rel: str, text: str) -> int:
    path = root / rel

    def edit() -> None:
        path.write_text(text, encoding="utf-8")
        os.utime(path, ns=(10**9, 10**9))

    requests = _Requests()
    live_watch.watch(requests, lambda: live_watch.watched(root), _Ticks(edit, lambda: None), 0)
    return requests.count


def test_the_watcher_watches_tsconfig_extends_and_references(tmp_path: Path) -> None:
    write_tree(tmp_path, TYPESCRIPT_TREE)
    found = _names(tmp_path)
    assert {
        "tsconfig.json",
        "tsconfig.base.json",
        "node_modules/@scope/tsconfig/strict.json",
        "tsconfig.build.json",
        "packages/lib/tsconfig.json",
        "config/tsconfig.shared.json",
        "package.json",
    } <= found
    assert "other/tsconfig.unused.json" not in found


def test_a_change_to_a_tsconfig_base_file_requests_a_render(tmp_path: Path) -> None:
    write_tree(tmp_path, TYPESCRIPT_TREE)
    assert _requests_after_edit(tmp_path, "tsconfig.base.json", '{"compilerOptions": {}}\n') == 1


def test_a_tsconfig_that_is_not_valid_or_a_cycle_does_not_stop_the_watcher(
    tmp_path: Path,
) -> None:
    write_tree(
        tmp_path,
        {
            **TYPESCRIPT_TREE,
            "tsconfig.json": '{"extends": "./a.json", "references": [{"path": "./b.json"}]}',
            "a.json": '{"extends": "./tsconfig.json"}',
            "b.json": "{ not json",
        },
    )
    assert {"tsconfig.json", "a.json", "b.json"} <= _names(tmp_path)


def test_the_watcher_watches_the_python_configuration(tmp_path: Path) -> None:
    write_tree(tmp_path, PYTHON_TREE)
    found = _names(tmp_path)
    assert {"systemap.toml", "pyproject.toml", "libs/core/pyproject.toml"} <= found
    assert "other/pyproject.toml" not in found
    assert _requests_after_edit(tmp_path, "pyproject.toml", '[project]\nname = "new"\n') == 1


def test_the_watched_configuration_comes_from_the_adapter_call(tmp_path: Path) -> None:
    for language, tree, folders in (
        ("typescript", TYPESCRIPT_TREE, ["src"]),
        ("python", PYTHON_TREE, ["libs/core/src/core"]),
    ):
        root = tmp_path / language
        write_tree(root, tree)
        shared = set(live_watch.CONFIG_FILES)
        expected = shared | _adapter_paths(root, language, folders)
        model_files = {
            p.relative_to(root).as_posix() for p in config.load(root).model_path.parent.glob("*.py")
        }
        assert _configs(root, language) - model_files == expected
