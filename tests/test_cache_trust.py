"""A cache file that Git tracks does not supply answers (llm-8).

A cloned repository can contain `.systemap/agent-cache.json` or a Jev cache with answers
that no agent or provider gave on this computer. The cache does not read or write such a
file unless the environment sets SYSTEMAP_TRUST_TRACKED_CACHE=1. Each sequence result
from the agent cache has the row "from the cache". The tests use an injected agent.
"""

from __future__ import annotations

import argparse
import json
import subprocess
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
    assert not jev.tracked(tmp_path, path)


def test_outside_a_repository_the_cache_file_is_used(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(json.dumps(PLANTED), encoding="utf-8")
    missing = tmp_path / "no-folder"
    assert not jev.tracked(missing, path)
    assert jev.Cache(path, root=tmp_path).entries == PLANTED["entries"]


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
