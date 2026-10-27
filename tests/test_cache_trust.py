"""A cache file that Git tracks does not supply answers (llm-8).

A cloned repository can contain `.systemap/agent-cache.json` or a Jev cache with answers
that no agent or provider gave on this computer. The cache does not read or write such a
file unless the environment sets SYSTEMAP_TRUST_TRACKED_CACHE=1. Each sequence result
from the agent cache has the row "from the cache". The tests use an injected agent.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config, jev, journeys, nest
from systemap.cli import main
from systemap.jev_cli import cmd_journeys

PLANTED = {"version": 1, "entries": {"k": {"prose": "planted"}}, "releases": {}}


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def planted_cache(root: Path, *, commit: bool) -> Path:
    path = root / ".systemap" / "agent-cache.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(PLANTED), encoding="utf-8")
    git(root, "init", "-q")
    if commit:
        git(root, "add", "-f", ".systemap/agent-cache.json")
        git(root, "commit", "-q", "-m", "clone")
    return path


def test_a_tracked_cache_file_is_not_read_or_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: before the change, the cache read the planted entry."""
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    path = planted_cache(tmp_path, commit=True)
    cache = jev.Cache(path, root=tmp_path)
    assert cache.refused
    assert cache.entries == {}
    err = capsys.readouterr().err
    assert "did not read or write the cache file .systemap/agent-cache.json" in err
    assert f"{jev.TRUST_TRACKED}=1" in err
    cache.entries["new"] = {"prose": "new"}
    cache.save()
    assert json.loads(path.read_text(encoding="utf-8")) == PLANTED


def test_the_trust_value_permits_a_tracked_cache_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(jev.TRUST_TRACKED, "1")
    path = planted_cache(tmp_path, commit=True)
    cache = jev.Cache(path, root=tmp_path)
    assert not cache.refused
    assert cache.entries == PLANTED["entries"]
    assert capsys.readouterr().err == ""


def test_an_untracked_cache_file_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    path = planted_cache(tmp_path, commit=False)
    assert jev.Cache(path, root=tmp_path).entries == PLANTED["entries"]
    assert not jev.tracked(path)


def test_outside_a_repository_the_cache_file_is_used(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(json.dumps(PLANTED), encoding="utf-8")
    assert not jev.tracked(path)
    assert not jev.tracked(tmp_path / "no-folder" / "c.json")
    assert jev.Cache(path, root=tmp_path).entries == PLANTED["entries"]


def submodule_cache(tmp_path: Path) -> Path:
    """A repository `top` has the submodule `vendor`. The submodule tracks c.json."""
    sub, top = tmp_path / "sub", tmp_path / "top"
    sub.mkdir()
    top.mkdir()
    git(sub, "init", "-q")
    (sub / "c.json").write_text(json.dumps(PLANTED), encoding="utf-8")
    git(sub, "add", "c.json")
    git(sub, "commit", "-q", "-m", "sub")
    git(top, "init", "-q")
    git(top, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendor")
    git(top, "commit", "-q", "-m", "top")
    return top


def test_a_cache_file_that_a_submodule_tracks_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: before the change, the check ran only in `top`. The cache then read
    the planted entry from the submodule file, and from a link to that file."""
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    top = submodule_cache(tmp_path)
    assert jev.tracked(top / "vendor" / "c.json")
    cache = jev.Cache(top / "vendor" / "c.json", root=top)
    assert cache.refused
    assert cache.entries == {}
    assert "remove the file from Git: git -C vendor rm --cached c.json" in capsys.readouterr().err
    link = top / ".systemap" / "link.json"
    link.parent.mkdir()
    link.symlink_to(top / "vendor" / "c.json")
    assert jev.tracked(link)
    assert jev.Cache(link, root=top).entries == {}


def test_a_different_case_of_a_tracked_name_is_tracked_only_if_it_is_the_same_file(
    tmp_path: Path,
) -> None:
    """The name comparison ignores the case of letters. On a file system that ignores the
    case, the two names are one file, and the result is True. Here they are two files."""
    path = planted_cache(tmp_path, commit=True)
    other = path.with_name("AGENT-CACHE.json")
    other.write_text(json.dumps(PLANTED), encoding="utf-8")
    assert jev.tracked(other) == other.samefile(path)


def answer(ident: str) -> str:
    step = {"edge": ["Reader", "Writer"], "acts": ["Reader"], "measures": [], "say": "s"}
    return json.dumps({"id": ident, "label": ident, "steps": [step]})


def route_project(root: Path) -> None:
    write_tree(
        root,
        {
            "pkg/__init__.py": "",
            **STARTER_MODULES,
            "pkg/reader.py": 'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/read")\n'
            "def read(source: str) -> str:\n    return source\n",
        },
    )
    init_two_cards(root, "--no-ci")
    assert main(["--root", str(root), "extract"]) == 0
    toml = root / "systemap.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + '\n[agent]\ncommand = "agent -p"\n')


def run_journeys(root: Path, text: str, calls: list[int]) -> int:
    def agent(*_args: object) -> str:
        calls.append(1)
        return text

    return cmd_journeys(argparse.Namespace(root_path=root, limit=3, dry_run=False), agent)


def ids(root: Path) -> list[str]:
    return [j.id for j in nest.load(config.load(root)).top.meaning.journeys]


def test_journeys_ignores_a_planted_tracked_agent_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (llm-8): a committed agent cache has the answer `planted`. The agent is
    asked, and its answer `honest` is written. Before the change, the agent got no call
    ("agent: 0 calls, 1 cached answers"), and the map got the planted sequence."""
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    route_project(tmp_path)
    model = (tmp_path / "map/model.py").read_text(encoding="utf-8")
    calls: list[int] = []
    assert run_journeys(tmp_path, answer("planted"), calls) == 0
    (tmp_path / "map/model.py").write_text(model, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A", "-f")
    git(tmp_path, "commit", "-q", "-m", "clone")
    capsys.readouterr()
    calls.clear()
    assert run_journeys(tmp_path, answer("honest"), calls) == 0
    said = capsys.readouterr()
    assert calls == [1]
    assert "honest" in ids(tmp_path) and "planted" not in ids(tmp_path)
    assert journeys.FROM_CACHE not in said.out
    assert "agent: 1 calls, 0 cached answers." in said.err
    assert "because Git tracks it" in said.err
    # With the trust value, the planted answer is used, and the result tells so.
    git(tmp_path, "checkout", "-q", "--", "map/model.py")
    monkeypatch.setenv(jev.TRUST_TRACKED, "1")
    calls.clear()
    assert run_journeys(tmp_path, answer("honest"), calls) == 0
    assert calls == []
    assert "planted" in ids(tmp_path)
    assert journeys.FROM_CACHE in capsys.readouterr().out


def test_each_sequence_from_the_cache_has_the_cache_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An untracked cache answer is used, and its result has the row "from the cache".
    A new answer from the agent has no such row."""
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    route_project(tmp_path)
    model = (tmp_path / "map/model.py").read_text(encoding="utf-8")
    calls: list[int] = []
    assert run_journeys(tmp_path, answer("first"), calls) == 0
    assert journeys.FROM_CACHE not in capsys.readouterr().out
    (tmp_path / "map/model.py").write_text(model, encoding="utf-8")
    assert run_journeys(tmp_path, answer("second"), calls) == 0
    out = capsys.readouterr().out
    assert calls == [1]
    assert "journeys: wrote first (first)" in out
    assert f"      {journeys.FROM_CACHE}" in out


def _failing_git(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put a Git program on PATH that refuses each repository as Git does for a different
    owner."""
    folder = tmp / "fakebin"
    folder.mkdir()
    program = folder / "git"
    program.write_text(
        "#!/bin/sh\necho \"fatal: detected dubious ownership in repository at '$PWD'\" >&2\n"
        "exit 128\n",
        encoding="utf-8",
    )
    program.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")


@pytest.mark.skipif(sys.platform == "win32", reason="the fake Git is a shell script")
def test_a_cache_file_in_a_work_tree_is_not_read_if_git_cannot_do_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (SEC-1): before the repair, a Git refusal gave "not tracked". Then the
    cache read the planted entry."""
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    path = planted_cache(tmp_path, commit=True)
    _failing_git(tmp_path, monkeypatch)
    cache = jev.Cache(path, root=tmp_path)
    assert cache.refused
    assert cache.entries == {}
    err = capsys.readouterr().err
    assert "Git cannot tell if it tracks the file" in err
    assert "detected dubious ownership" in err
    monkeypatch.setenv(jev.TRUST_TRACKED, "1")
    assert jev.Cache(path, root=tmp_path).entries == PLANTED["entries"]


@pytest.mark.skipif(sys.platform == "win32", reason="the fake Git is a shell script")
def test_outside_a_work_tree_a_git_refusal_does_not_stop_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    path = tmp_path / "c.json"
    path.write_text(json.dumps(PLANTED), encoding="utf-8")
    _failing_git(tmp_path, monkeypatch)
    assert jev.Cache(path, root=tmp_path).entries == PLANTED["entries"]


def test_the_cache_warning_shows_control_characters_as_escapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (SEC-5): before the repair, ESC and BEL of the cache name reached stderr."""
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    name = "c\x1b]0;PWNED\x07\x1b[2J.json"
    path = tmp_path / name
    try:
        path.write_text(json.dumps(PLANTED), encoding="utf-8")
    except OSError as exc:
        # Windows refuses control characters in a file name, so such a cache cannot exist.
        pytest.skip(f"the file system refuses this file name: {exc}")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-f", "--", name)
    git(tmp_path, "commit", "-q", "-m", "clone")
    assert jev.Cache(path, root=tmp_path).refused
    err = capsys.readouterr().err
    assert "\x1b" not in err and "\x07" not in err
    assert "c\\u001b]0;PWNED\\u0007" in err
