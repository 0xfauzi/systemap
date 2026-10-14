"""Each cache and output file stays in its stated root, for a read and for a write.

Before this change, `file_write` confined a path only to the folder of the file. Thus a
cache folder, or a parent folder, that is a link out of the repository let a command read
and write a file outside the repository. A configured cache path or output path could be
absolute, or contain `..`. `plan.save` and the page writes wrote through a link. A refused
source file was left out of a decision request with no cause, and its evidence said
"missing source". `pyproject.toml` that is not valid TOML gave an empty table.

Acceptance, written before the change:

1. A configured `[jev]`, `[openai]`, or `[agent]` cache, `out_dir`, or `model` that is
   absolute or that has a `..` part gives a ConfigError at load time.
2. A link out of the repository at the cache folder or at one parent folder gives
   `RefusedFile` for a read, a write, and a lock. No file outside the repository changes.
   The same applies to the facts cache, the decision store, a plan, and the output
   directory.
3. A write of a plan or a page replaces a link. It does not write through it.
4. A source file that is a link out of the repository, or that is not a regular file,
   gives its cause in the decision request (the file record and `blocked`), and in the
   evidence state.
5. `pyproject.toml` that is not valid TOML gives a ConfigError with the parse error.
   An invalid `tsconfig.json` also gives a ConfigError in extraction.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import (
    config,
    decisions,
    decisions_store,
    extract,
    file_write,
    history,
    jev,
    judgement_evidence,
    plan,
    python_repo,
)
from systemap import language as languages
from systemap.cli import main
from systemap.config import ConfigError

NOT_IN_ROOT = "is not in"
SYSTEMAP_TOML = 'language = "python"\nname = "pkg"\n[package_roots]\n"pkg" = "pkg"\n'
STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


@pytest.fixture
def layout(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """Give a repository folder and a folder outside it."""
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    yield repo, outside


def _python_repo(repo: Path, extra: str = "") -> config.Config:
    write_tree(
        repo, {"systemap.toml": extra + SYSTEMAP_TOML, "pkg/__init__.py": "def main(): ...\n"}
    )
    return config.load(repo)


def _files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*"))


# ---- 1. configured paths that the tool writes ----------------------------------------

CONFIGURED = [
    '[jev]\ncache = "/tmp/systemap-jev.json"\n',
    '[jev]\ncache = "../jev.json"\n',
    '[openai]\ncache = "../../openai.json"\n',
    '[agent]\ncache = "/tmp/agent.json"\n',
    'out_dir = "../site"\n',
    'out_dir = "/tmp/site"\n',
    'model = "../model.py"\n',
]


@pytest.mark.parametrize("table", CONFIGURED)
def test_a_configured_path_out_of_the_repository_is_a_configuration_error(
    tmp_path: Path, table: str
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": ""})
    top = "\n".join(line for line in table.splitlines() if not line.startswith("[")) + "\n"
    head, body = (table, "") if table.startswith("[") else ("", top)
    (tmp_path / "systemap.toml").write_text(
        body + 'language = "python"\nname = "pkg"\n[package_roots]\n"pkg" = "pkg"\n' + head,
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="not in the repository"):
        config.load(tmp_path)


def test_a_configured_path_in_the_repository_is_accepted(tmp_path: Path) -> None:
    cfg = _python_repo(tmp_path, 'out_dir = "site/map"\n')
    assert cfg.out_dir == "site/map"


# ---- 2. a link at a folder level ---------------------------------------------------

LEVELS = ["state/jev", "state"]


def _linked(repo: Path, outside: Path, level: str) -> None:
    """Make the folder `level` of the repository a link to the outside folder."""
    target = outside / level.replace("/", "-")
    (target / "jev").mkdir(parents=True, exist_ok=True)
    held = {"version": 1, "entries": {"key": "leaked"}, "releases": {}}
    destination = target if level == "state/jev" else target / "jev"
    (destination / "cache.json").write_text(json.dumps(held), encoding="utf-8")
    link = repo / level
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize("level", LEVELS)
def test_a_cache_read_through_a_folder_link_is_refused(
    layout: tuple[Path, Path], level: str
) -> None:
    repo, outside = layout
    _linked(repo, outside, level)
    with pytest.raises(file_write.RefusedFile, match=NOT_IN_ROOT):
        jev.Cache(repo / "state/jev/cache.json", root=repo)


def _save(path: Path, root: Path) -> None:
    """Make a cache, add one entry, and save it. A refusal can occur at each step."""
    cache = jev.Cache(path, root=root)
    cache.entries["key"] = "value"
    cache.save()


@pytest.mark.parametrize("level", LEVELS)
def test_a_cache_write_through_a_folder_link_is_refused(
    layout: tuple[Path, Path], level: str
) -> None:
    repo, outside = layout
    _linked(repo, outside, level)
    for path in outside.rglob("cache.json"):
        path.unlink()
    before = _files(outside)
    with pytest.raises(file_write.RefusedFile, match=NOT_IN_ROOT):
        _save(repo / "state/jev/cache.json", repo)
    assert _files(outside) == before


def test_a_cache_folder_that_does_not_exist_below_a_link_is_not_made(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    (repo / "state").symlink_to(outside, target_is_directory=True)
    with pytest.raises(file_write.RefusedFile, match=NOT_IN_ROOT):
        _save(repo / "state/new/cache.json", repo)
    assert _files(outside) == []


def test_a_cache_file_needs_its_root() -> None:
    with pytest.raises(ValueError, match="root"):
        jev.Cache(Path("cache.json"))


def test_a_cache_with_a_dot_dot_part_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    with pytest.raises(file_write.RefusedFile, match="without a .. part"):
        _save(repo / ".." / "outside" / "cache.json", repo)
    assert _files(outside) == []


@pytest.mark.parametrize("level", LEVELS)
def test_a_lock_through_a_folder_link_is_refused(layout: tuple[Path, Path], level: str) -> None:
    repo, outside = layout
    _linked(repo, outside, level)
    before = _files(outside)
    with (
        pytest.raises(file_write.RefusedFile, match=NOT_IN_ROOT),
        file_write.locked(repo, repo / "state/jev/cache.json"),
    ):
        pass
    assert _files(outside) == before


def test_the_facts_cache_through_a_folder_link_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    cfg = _python_repo(repo)
    (repo / ".systemap").symlink_to(outside, target_is_directory=True)
    with pytest.raises(file_write.RefusedFile, match=NOT_IN_ROOT):
        history.facts_at(cfg, "a" * 40)
    assert _files(outside) == []


def test_the_decision_store_through_a_folder_link_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    (repo / ".systemap").symlink_to(outside, target_is_directory=True)
    with pytest.raises(file_write.RefusedFile, match=NOT_IN_ROOT):
        decisions_store.save(repo, {})
    assert _files(outside) == []


def test_a_plan_through_a_folder_link_is_refused(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    cfg = _python_repo(repo)
    (repo / ".systemap").symlink_to(outside, target_is_directory=True)
    with pytest.raises(file_write.RefusedFile, match=NOT_IN_ROOT):
        plan.load(cfg, "p1")
    assert _files(outside) == []


def _rendered(repo: Path) -> None:
    write_tree(repo, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(repo, "--no-ci")
    assert main(["--root", str(repo), "refresh"]) == 0


def test_an_output_folder_link_out_of_the_repository_is_refused(
    layout: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, outside = layout
    _rendered(repo)
    (repo / "docs/map").rename(outside / "map")
    (repo / "docs/map").symlink_to(outside / "map", target_is_directory=True)
    before = {p: p.read_bytes() for p in (outside / "map").rglob("*") if p.is_file()}
    capsys.readouterr()
    assert main(["--root", str(repo), "refresh"]) != 0
    assert "not in" in capsys.readouterr().err
    after = {p: p.read_bytes() for p in (outside / "map").rglob("*") if p.is_file()}
    assert after == before


# ---- 3. a write replaces a link ---------------------------------------------------


def test_a_plan_save_replaces_a_dangling_link(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    cfg = _python_repo(repo)
    projection = plan.Projection(id="p1", task="task", at="20261013")
    path = plan.path_of(cfg, "p1")
    path.parent.mkdir(parents=True)
    path.symlink_to(outside / "made.json")
    plan.save(cfg, projection)
    assert _files(outside) == []
    assert not path.is_symlink()


def test_a_page_write_replaces_a_link_in_the_output_directory(tmp_path: Path) -> None:
    _rendered(tmp_path)
    page = tmp_path / "docs/map/index.html"
    other = tmp_path / "docs/map/other.html"
    other.write_text("keep", encoding="utf-8")
    page.unlink()
    page.symlink_to(other)
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert other.read_text(encoding="utf-8") == "keep"
    assert not page.is_symlink()


def test_a_facts_write_replaces_a_link_in_the_output_directory(tmp_path: Path) -> None:
    _rendered(tmp_path)
    facts = tmp_path / "docs/map/map.json"
    other = tmp_path / "docs/map/other.json"
    other.write_bytes(facts.read_bytes())
    facts.unlink()
    facts.symlink_to(other)
    before = other.read_bytes()
    (tmp_path / "pkg/reader.py").write_text("def read(s: str) -> int:\n    return 1\n")
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert other.read_bytes() == before
    assert not facts.is_symlink()


# ---- 4. the cause of a refused source file ----------------------------------------


def _facts(name: str) -> dict[str, Any]:
    return {"components": {"pkg.a": {"file": name}}}


def test_a_source_link_out_of_the_repository_gives_its_cause(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    (outside / "a.py").write_text("SECRET = 1\n", encoding="utf-8")
    (repo / "pkg").mkdir()
    (repo / "pkg/a.py").symlink_to(outside / "a.py")
    files = decisions._files(repo, _facts("pkg/a.py"), ["pkg.a"])
    assert [(f.file, f.problem) for f in files] == [("pkg/a.py", "link out of the repository")]
    assert "pkg/a.py" in decisions.blocked_by("", files)
    assert "link out of the repository" in decisions.blocked_by("", files)
    state = judgement_evidence.full_state(_facts("pkg/a.py")["components"], repo, "", behavior=True)
    assert "link out of the repository" in json.dumps(state)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="The platform has no FIFO.")
def test_a_fifo_source_gives_its_cause(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    os.mkfifo(tmp_path / "pkg/a.py")
    files = decisions._files(tmp_path, _facts("pkg/a.py"), ["pkg.a"])
    cause = "not a regular file in the repository"
    assert [(f.file, f.problem) for f in files] == [("pkg/a.py", cause)]
    state = judgement_evidence.full_state(
        _facts("pkg/a.py")["components"], tmp_path, "", behavior=True
    )
    assert cause in json.dumps(state)


def test_a_missing_source_keeps_its_evidence_text(tmp_path: Path) -> None:
    state = judgement_evidence.full_state(
        _facts("pkg/a.py")["components"], tmp_path, "", behavior=True
    )
    assert "missing source" in json.dumps(state)


# ---- 5. configuration files that are not valid ------------------------------------


def test_a_pyproject_that_is_not_toml_gives_the_parse_error(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\nname = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="pyproject.toml") as caught:
        python_repo.pyproject(tmp_path)
    assert "line 1" in str(caught.value)


def test_a_tsconfig_that_is_not_json_stops_extraction(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name": "web"}\n',
            "tsconfig.json": "{ not json",
            "src/index.ts": "export const one = 1;\n",
        },
    )
    with pytest.raises(ConfigError, match="tsconfig.json"):
        extract.build(config.load(tmp_path))
    assert languages.adapter("typescript")
