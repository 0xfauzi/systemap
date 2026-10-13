"""Each read of a repository file, an output file, or a cache file is confined.

Before this change, these reads used `Path.read_text`, `Path.read_bytes`, or `open`:

- `pyproject.toml` in the Python adapter (`python_repo.pyproject` and
  `python_entry.read_pyproject`),
- the language configuration files in the facts provenance (`extraction._provenance`),
- the page and the figures that `systemap check` compares (`check._stale_file`),
- the facts file (`facts_file.read_facts`),
- the Jev, OpenAI, and agent cache (`jev.Cache`), the facts cache (`history.facts_at`),
  the decision store (`decisions_store.load`), and a plan (`plan.load`),
- the lock file of a cache (`file_write.locked`),
- the model file (`config.load_model`).

A link out of the repository, or out of the folder of the file, was read. A FIFO made a
cache read or a lock wait with no end. A FIFO repository file or output file gave the
result of a missing file.

Acceptance, written before the change. For each read in the list:

- A link to a file out of the repository (or out of the folder of an output or a cache
  file) gives an error that names the file and the cause. The command does not use the
  content of the file outside.
- A FIFO gives an error with the cause "not a regular file" in less than 5 seconds.
  The FIFO tests do not operate on Windows.
- A missing file gives the same result as before.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import (
    config,
    decisions_store,
    extraction,
    facts_file,
    file_write,
    history,
    jev,
    plan,
    python_entry,
    python_repo,
)
from systemap import language as languages
from systemap.cli import main
from systemap.config import ConfigError

FIFO = pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="The platform has no FIFO.")
OUTSIDE_LINK = "not in the repository"
OUTSIDE_FOLDER = "in a different folder"
NOT_REGULAR = "not a regular file"
WAIT = 5.0

PYPROJECT_OUTSIDE = '[project]\nname = "leaked"\n[project.scripts]\nleak = "pkg:main"\n'
STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}
SYSTEMAP_TOML = 'language = "python"\nname = "pkg"\n[package_roots]\n"pkg" = "pkg"\n'


@pytest.fixture
def layout(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """Give a repository folder and a folder outside it."""
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    yield repo, outside


def _release(fifo: Path) -> None:
    """Let a reader that waits on the FIFO continue: open it for writing, then close it."""
    try:
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
    except OSError:
        pass


def _outcome(call: Callable[[], Any], fifo: Path | None = None) -> tuple[str, Any]:
    """Operate the call in a thread. Give ("value", v), ("error", exc), or ("waited", None).

    If the call does not stop in WAIT seconds, the FIFO gets a writer, and the result is
    "waited".
    """
    found: list[tuple[str, Any]] = []

    def target() -> None:
        try:
            found.append(("value", call()))
        except Exception as exc:  # noqa: BLE001 - the test examines each error
            found.append(("error", exc))

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(WAIT)
    if thread.is_alive():
        if fifo is not None:
            _release(fifo)
        thread.join(WAIT)
        return "waited", None
    return found[0]


def _refused(outcome: tuple[str, Any], cause: str, name: str) -> None:
    kind, value = outcome
    assert kind == "error", f"the read gave {kind}: {value!r}"
    assert cause in str(value), str(value)
    assert name in str(value), str(value)


def _python_repo(repo: Path) -> config.Config:
    write_tree(repo, {"systemap.toml": SYSTEMAP_TOML, "pkg/__init__.py": "def main(): ...\n"})
    return config.load(repo)


# ---- pyproject.toml in the Python adapter ---------------------------------------------

PYPROJECT_READERS: list[Callable[[Path], dict[str, Any]]] = [
    python_repo.pyproject,
    python_entry.read_pyproject,
]


@pytest.mark.parametrize("read", PYPROJECT_READERS)
def test_a_pyproject_link_out_of_the_repository_is_refused(
    layout: tuple[Path, Path], read: Callable[[Path], dict[str, Any]]
) -> None:
    repo, outside = layout
    (outside / "pyproject.toml").write_text(PYPROJECT_OUTSIDE, encoding="utf-8")
    (repo / "pyproject.toml").symlink_to(outside / "pyproject.toml")
    _refused(_outcome(lambda: read(repo)), OUTSIDE_LINK, "pyproject.toml")


@FIFO
@pytest.mark.parametrize("read", PYPROJECT_READERS)
def test_a_fifo_pyproject_is_refused(
    tmp_path: Path, read: Callable[[Path], dict[str, Any]]
) -> None:
    os.mkfifo(tmp_path / "pyproject.toml")
    _refused(
        _outcome(lambda: read(tmp_path), tmp_path / "pyproject.toml"), NOT_REGULAR, "pyproject.toml"
    )


@pytest.mark.parametrize("read", PYPROJECT_READERS)
def test_a_missing_pyproject_gives_an_empty_table(
    tmp_path: Path, read: Callable[[Path], dict[str, Any]]
) -> None:
    assert read(tmp_path) == {}


# ---- the configuration files in the facts provenance -----------------------------------


def test_a_provenance_configuration_link_out_of_the_repository_is_refused(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    cfg = _python_repo(repo)
    (outside / "pyproject.toml").write_text(PYPROJECT_OUTSIDE, encoding="utf-8")
    (repo / "pyproject.toml").symlink_to(outside / "pyproject.toml")
    adapter = languages.adapter("python")
    _refused(
        _outcome(lambda: extraction._provenance(cfg, adapter, None)), OUTSIDE_LINK, "pyproject.toml"
    )


@FIFO
def test_a_fifo_provenance_configuration_is_refused(tmp_path: Path) -> None:
    cfg = _python_repo(tmp_path)
    os.mkfifo(tmp_path / "pyproject.toml")
    adapter = languages.adapter("python")
    outcome = _outcome(
        lambda: extraction._provenance(cfg, adapter, None), tmp_path / "pyproject.toml"
    )
    _refused(outcome, NOT_REGULAR, "pyproject.toml")


def test_a_missing_provenance_configuration_has_no_digest(tmp_path: Path) -> None:
    cfg = _python_repo(tmp_path)
    provenance = extraction._provenance(cfg, languages.adapter("python"), None)
    assert provenance["files"] == {}


# ---- the output files that check compares ---------------------------------------------


def _rendered(repo: Path) -> Path:
    write_tree(repo, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(repo, "--no-ci")
    assert main(["--root", str(repo), "refresh"]) == 0
    assert main(["--root", str(repo), "check"]) == 0
    return repo / "docs/map/figures/system.svg"


def test_check_refuses_a_figure_link_out_of_the_output_directory(
    layout: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, outside = layout
    figure = _rendered(repo)
    copy = outside / "system.svg"
    copy.write_bytes(figure.read_bytes())
    figure.unlink()
    figure.symlink_to(copy)
    capsys.readouterr()
    assert main(["--root", str(repo), "check"]) != 0
    err = capsys.readouterr().err
    assert "system.svg" in err
    assert "not in the output directory" in err


@FIFO
def test_check_refuses_a_fifo_figure_with_its_cause(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    figure = _rendered(tmp_path)
    figure.unlink()
    os.mkfifo(figure)
    capsys.readouterr()
    kind, code = _outcome(lambda: main(["--root", str(tmp_path), "check"]), figure)
    assert (kind, code != 0) == ("value", True)
    err = capsys.readouterr().err
    assert "system.svg" in err
    assert NOT_REGULAR in err


# ---- the facts file -----------------------------------------------------------------


def test_a_facts_file_link_out_of_its_folder_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    (outside / "map.json").write_text('{"leaked": true}', encoding="utf-8")
    (repo / "map.json").symlink_to(outside / "map.json")
    _refused(_outcome(lambda: facts_file.read_facts(repo / "map.json")), OUTSIDE_FOLDER, "map.json")


@FIFO
def test_a_fifo_facts_file_is_refused(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "map.json")
    outcome = _outcome(lambda: facts_file.read_facts(tmp_path / "map.json"), tmp_path / "map.json")
    _refused(outcome, NOT_REGULAR, "map.json")


def test_a_facts_file_name_out_of_the_output_directory_is_refused(
    layout: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, outside = layout
    (outside / "map.json").write_text('{"leaked": true}', encoding="utf-8")
    _rendered(repo)
    toml = repo / "systemap.toml"
    toml.write_text(
        'facts_file = "../../../outside/map.json"\n' + toml.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert main(["--root", str(repo), "check"]) != 0
    captured = capsys.readouterr()
    assert "is not in the output directory" in captured.err, captured.out


def test_a_missing_facts_file_gives_an_empty_table(tmp_path: Path) -> None:
    assert facts_file.read_facts(tmp_path / "map.json") == {}


# ---- the caches ----------------------------------------------------------------------

CACHE_OUTSIDE = {"version": 1, "entries": {"key": "leaked"}, "releases": {}}


def test_a_jev_cache_link_out_of_its_folder_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    (outside / "cache.json").write_text(json.dumps(CACHE_OUTSIDE), encoding="utf-8")
    (repo / "cache.json").symlink_to(outside / "cache.json")
    _refused(_outcome(lambda: jev.Cache(repo / "cache.json").entries), OUTSIDE_FOLDER, "cache.json")


@FIFO
def test_a_fifo_jev_cache_is_refused(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "cache.json")
    outcome = _outcome(lambda: jev.Cache(tmp_path / "cache.json"), tmp_path / "cache.json")
    _refused(outcome, NOT_REGULAR, "cache.json")


def test_a_missing_jev_cache_is_empty(tmp_path: Path) -> None:
    assert jev.Cache(tmp_path / "cache.json").entries == {}


SHA = "a" * 40


def _facts_cache(cfg: config.Config) -> Path:
    scope = history.cache_scope(cfg, languages.repository(cfg.language).parser_version())
    path = history.cache_dir(cfg) / f"{SHA}-{scope}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_a_facts_cache_link_out_of_its_folder_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    cfg = _python_repo(repo)
    (outside / "facts.json").write_text('{"leaked": true}', encoding="utf-8")
    path = _facts_cache(cfg)
    path.symlink_to(outside / "facts.json")
    _refused(_outcome(lambda: history.facts_at(cfg, SHA)), OUTSIDE_FOLDER, path.name)


@FIFO
def test_a_fifo_facts_cache_is_refused(tmp_path: Path) -> None:
    cfg = _python_repo(tmp_path)
    path = _facts_cache(cfg)
    os.mkfifo(path)
    _refused(_outcome(lambda: history.facts_at(cfg, SHA), path), NOT_REGULAR, path.name)


def _store(repo: Path) -> Path:
    path = decisions_store.path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_a_decision_store_link_out_of_its_folder_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    held = {"version": decisions_store.VERSION, "records": {"key": {"verdict": "supported"}}}
    (outside / "decisions.json").write_text(json.dumps(held), encoding="utf-8")
    _store(repo).symlink_to(outside / "decisions.json")
    _refused(_outcome(lambda: decisions_store.load(repo)), OUTSIDE_FOLDER, "decisions.json")


@FIFO
def test_a_fifo_decision_store_is_refused(tmp_path: Path) -> None:
    path = _store(tmp_path)
    os.mkfifo(path)
    _refused(_outcome(lambda: decisions_store.load(tmp_path), path), NOT_REGULAR, "decisions.json")


def test_a_missing_decision_store_has_no_records(tmp_path: Path) -> None:
    assert decisions_store.load(tmp_path) == {}


def _plan(cfg: config.Config) -> Path:
    path = plan.path_of(cfg, "p1")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_a_plan_link_out_of_its_folder_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    cfg = _python_repo(repo)
    (outside / "p1.json").write_text('{"task": "leaked"}', encoding="utf-8")
    _plan(cfg).symlink_to(outside / "p1.json")
    _refused(_outcome(lambda: plan.load(cfg, "p1")), OUTSIDE_FOLDER, "p1.json")


@FIFO
def test_a_fifo_plan_is_refused(tmp_path: Path) -> None:
    cfg = _python_repo(tmp_path)
    path = _plan(cfg)
    os.mkfifo(path)
    _refused(_outcome(lambda: plan.load(cfg, "p1"), path), NOT_REGULAR, "p1.json")


def test_a_missing_plan_gives_none(tmp_path: Path) -> None:
    assert plan.load(_python_repo(tmp_path), "p1") is None


# ---- the lock file of a cache --------------------------------------------------------


def _hold(path: Path) -> bool:
    with file_write.locked(path):
        return True


def test_a_lock_link_is_refused_and_makes_no_file_outside(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    (repo / "cache.json.lock").symlink_to(outside / "made.lock")
    _refused(_outcome(lambda: _hold(repo / "cache.json")), "link", "cache.json.lock")
    assert not (outside / "made.lock").exists()


@FIFO
def test_a_fifo_lock_is_refused(tmp_path: Path) -> None:
    lock = tmp_path / "cache.json.lock"
    os.mkfifo(lock)
    _refused(_outcome(lambda: _hold(tmp_path / "cache.json"), lock), NOT_REGULAR, lock.name)


def test_a_missing_lock_is_made(tmp_path: Path) -> None:
    assert _hold(tmp_path / "cache.json")
    assert (tmp_path / "cache.json.lock").is_file()


# ---- the model file ------------------------------------------------------------------


@FIFO
def test_a_fifo_model_file_gives_its_cause(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "model.py")
    outcome = _outcome(lambda: config.load_model(tmp_path / "model.py"), tmp_path / "model.py")
    _refused(outcome, NOT_REGULAR, "model.py")
    assert isinstance(outcome[1], ConfigError)
