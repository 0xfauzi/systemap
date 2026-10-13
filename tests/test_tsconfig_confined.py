"""The tsconfig readers read only regular files in the repository.

Before this change, extraction and the live watcher read each `extends` and `references`
target with `Path.read_text`. Thus they read an absolute target, a `../` target, and a
link target outside the repository. A FIFO as a `references` target stopped the
watcher, because the open of a FIFO waits for a writer.

Acceptance, written before the change. For each of these targets:

- an absolute `extends` target outside the repository,
- a `../` `extends` target outside the repository,
- a `references` target that is a FIFO in the repository,
- an `extends` target that is a link in the repository to a file outside it,

extraction stops with a ConfigError that gives the path and the cause. The watcher does
not open the file, gives its result in less than 5 seconds, and its result does not
include a path outside the repository. A target in the node_modules folder of the
repository stays permitted.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, extract, live_watch
from systemap.config import ConfigError

_OPENED: list[str] = []
_ACTIVE = [False]


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if _ACTIVE[0] and event == "open" and args and isinstance(args[0], str | bytes | Path):
        _OPENED.append(os.fsdecode(args[0]))


sys.addaudithook(_hook)


def _tree(extends: str, references: list[str] | None = None) -> dict[str, str]:
    tsconfig: dict[str, Any] = {"extends": extends}
    if references is not None:
        tsconfig = {"references": [{"path": path} for path in references]}
    return {
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
        "package.json": '{"name": "web"}\n',
        "tsconfig.json": json.dumps(tsconfig),
        "src/index.ts": "export const one = 1;\n",
    }


@pytest.fixture
def layout(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """Give a repository folder and a file outside it with tsconfig settings."""
    repo = tmp_path / "repo"
    outside = tmp_path / "outside" / "secret.json"
    write_tree(tmp_path, {"outside/secret.json": '{"compilerOptions": {"strict": true}}'})
    repo.mkdir()
    yield repo, outside


def _watched(repo: Path) -> tuple[list[Path] | None, list[str]]:
    """Operate the watcher in a thread. Give its result, or None after 5 seconds."""
    found: list[list[Path]] = []
    _OPENED.clear()
    _ACTIVE[0] = True
    try:
        thread = threading.Thread(target=lambda: found.append(live_watch.watched(repo)))
        thread.daemon = True
        thread.start()
        thread.join(5)
    finally:
        _ACTIVE[0] = False
    return (found[0] if found else None), list(_OPENED)


def _assert_confined(repo: Path, outside: Path, cause: str, target: Path) -> None:
    """Examine the watcher first, and then extraction. Report the two results together."""
    paths, opened = _watched(repo)
    try:
        extract.build(config.load(repo))
        error = ""
    except ConfigError as exc:
        error = str(exc)
    problems = []
    if paths is None:
        problems.append("the watcher did not give a result in 5 seconds")
    elif [path for path in paths if not path.resolve().is_relative_to(repo.resolve())]:
        problems.append("the watcher gives a path outside the repository")
    if [path for path in opened if Path(path).resolve() == outside.resolve()]:
        problems.append("the watcher opened the file outside the repository")
    if cause not in error or target.resolve().as_posix() not in error:
        problems.append(f"extraction did not give the path and the cause: {error!r}")
    assert problems == []


def test_an_absolute_extends_target_outside_the_repository(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    write_tree(repo, _tree(str(outside)))
    _assert_confined(repo, outside, "not in the repository", outside)


def test_a_parent_extends_target_outside_the_repository(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    write_tree(repo, _tree("../outside/secret.json"))
    _assert_confined(repo, outside, "not in the repository", outside)


def test_a_link_to_a_file_outside_the_repository(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    write_tree(repo, _tree("./tsconfig.base.json"))
    (repo / "tsconfig.base.json").symlink_to(outside)
    _assert_confined(repo, outside, "not in the repository", outside)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="The platform has no FIFO.")
def test_a_references_target_that_is_a_fifo(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    write_tree(repo, _tree("", references=["./pipe.json"]))
    fifo = repo / "pipe.json"
    os.mkfifo(fifo)
    try:
        _assert_confined(repo, outside, "not a regular file", fifo)
    finally:
        _release(fifo)


def _release(fifo: Path) -> None:
    """Let a reader that waits on the FIFO continue: open it for writing, then close it."""
    try:
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
    except OSError:
        pass


def test_a_node_modules_extends_target_is_permitted(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            **_tree("@scope/base/tsconfig.json"),
            "node_modules/@scope/base/tsconfig.json": '{"compilerOptions": {"strict": true}}',
        },
    )
    extract.build(config.load(tmp_path))
    paths, _opened = _watched(tmp_path)
    assert paths is not None
    assert tmp_path / "node_modules/@scope/base/tsconfig.json" in paths


def test_a_nested_tsconfig_link_out_of_the_repository_stops_extraction(
    layout: tuple[Path, Path],
) -> None:
    """A nested tsconfig.json that is a link out of the repository is not silently
    replaced by the tsconfig.json file of a parent folder."""
    repo, outside = layout
    write_tree(repo, _tree("", references=[]))
    (repo / "src" / "tsconfig.json").symlink_to(outside)
    with pytest.raises(ConfigError, match="not in the repository"):
        extract.build(config.load(repo))


# ---- package.json and the systemap configuration --------------------------------------


def _package_tree() -> dict[str, str]:
    tree = _tree("", references=[])
    del tree["package.json"]
    return tree


def test_a_package_json_link_out_of_the_repository_stops_extraction(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    write_tree(repo, _package_tree())
    (repo / "package.json").symlink_to(outside)
    with pytest.raises(ConfigError, match="not in the repository") as caught:
        extract.build(config.load(repo))
    assert "package.json" in str(caught.value)


def test_an_installed_typescript_package_json_link_out_of_the_repository(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    write_tree(repo, {**_tree("", references=[]), "node_modules/typescript/.keep": ""})
    (repo / "node_modules" / "typescript" / "package.json").symlink_to(outside)
    with pytest.raises(ConfigError, match="not in the repository"):
        extract.build(config.load(repo))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="The platform has no FIFO.")
def test_a_fifo_package_json_stops_extraction(tmp_path: Path) -> None:
    write_tree(tmp_path, _package_tree())
    fifo = tmp_path / "package.json"
    os.mkfifo(fifo)
    try:
        with pytest.raises(ConfigError, match="not a regular file") as caught:
            extract.build(config.load(tmp_path))
        assert "package.json" in str(caught.value)
    finally:
        _release(fifo)


def test_a_systemap_toml_link_out_of_the_repository_is_a_configuration_error(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    write_tree(repo, {"src/index.ts": "export const one = 1;\n"})
    outside.write_text('language = "typescript"\n', encoding="utf-8")
    (repo / "systemap.toml").symlink_to(outside)
    with pytest.raises(ConfigError, match="not in the repository"):
        config.load(repo)
