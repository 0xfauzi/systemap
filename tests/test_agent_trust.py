"""The repository agent command starts only with the permission of the person.

A cloned repository can set any command under `[agent]`. systemap starts that command
only if the environment of the command sets SYSTEMAP_TRUST_AGENT_COMMAND=1. Each test
uses a fixture agent: a short Python program that writes a marker file. No test starts
a coding agent. Without the permission, the marker file must stay absent.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import agent, model_load
from systemap.cli import main
from systemap.config import load


def marker_agent(marker: Path) -> str:
    """Give the command of a fixture agent that writes the marker file and answers "no"."""
    code = (
        "import pathlib, sys; sys.stdin.read(); "
        f"pathlib.Path({str(marker)!r}).write_text('ran'); print('no')"
    )
    return shlex.join([sys.executable, "-c", code])


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    """A two-card map with an entry point and a marker agent under [agent]."""
    root, marker = tmp_path / "repo", tmp_path / "AGENT_MARKER"
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
    command = json.dumps(marker_agent(marker))
    toml.write_text(
        toml.read_text(encoding="utf-8") + f"\n[agent]\ncommand = {command}\n", encoding="utf-8"
    )
    return root, marker


def test_without_the_permission_the_command_does_not_start(tmp_path: Path) -> None:
    marker = tmp_path / "AGENT_MARKER"
    with pytest.raises(agent.AgentError) as caught:
        agent.shell_run(marker_agent(marker), "question", tmp_path, 30.0)
    assert not marker.exists()
    assert f"{agent.TRUST}=1" in str(caught.value)
    assert "If you trust this repository" in str(caught.value)


def test_with_the_permission_the_command_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(agent.TRUST, "1")
    marker = tmp_path / "AGENT_MARKER"
    assert agent.shell_run(marker_agent(marker), "question", tmp_path, 30.0).strip() == "no"
    assert marker.read_text() == "ran"


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "1 ", "01"])
def test_only_the_value_1_gives_the_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(agent.TRUST, value)
    marker = tmp_path / "AGENT_MARKER"
    with pytest.raises(agent.AgentError, match=agent.TRUST):
        agent.shell_run(marker_agent(marker), "question", tmp_path, 30.0)
    assert not marker.exists()


def test_the_model_code_permission_does_not_give_the_agent_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(model_load.TRUST, "1")
    assert agent.TRUST != model_load.TRUST
    marker = tmp_path / "AGENT_MARKER"
    with pytest.raises(agent.AgentError, match=agent.TRUST):
        agent.shell_run(marker_agent(marker), "question", tmp_path, 30.0)
    assert not marker.exists()


def test_from_cfg_refuses_the_repository_command_without_the_permission(
    repo: tuple[Path, Path],
) -> None:
    root, marker = repo
    cfg = load(root)
    with pytest.raises(agent.AgentError, match=agent.TRUST):
        agent.from_cfg(cfg)
    # An injected runner does not start the repository command. It needs no permission.
    writer = agent.from_cfg(cfg, lambda command, question, cwd, timeout: "answer")
    assert writer.ask("question") == "answer"
    assert not marker.exists()


def test_journeys_stops_with_exit_1_and_names_the_variable(
    repo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, marker = repo
    before = (root / "map" / "model.py").read_text(encoding="utf-8")
    assert main(["--root", str(root), "journeys"]) == 1
    out = capsys.readouterr().out
    assert f"{agent.TRUST}=1" in out
    assert agent.NO_AGENT not in out, "the command must not give the no-agent output"
    assert not marker.exists()
    assert (root / "map" / "model.py").read_text(encoding="utf-8") == before


def test_journeys_with_the_permission_starts_the_command(
    repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, marker = repo
    monkeypatch.setenv(agent.TRUST, "1")
    # The fixture agent answers "no", which is not a sequence. The command starts it.
    assert main(["--root", str(root), "journeys"]) == 1
    assert marker.read_text() == "ran"


def test_a_dry_run_works_without_the_permission_and_gives_the_step(
    repo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, marker = repo
    assert main(["--root", str(root), "journeys", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "GET /read (route)" in out
    assert f"{agent.TRUST}=1" in out
    assert not marker.exists()


def test_a_dry_run_with_the_permission_gives_no_step(
    repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, marker = repo
    monkeypatch.setenv(agent.TRUST, "1")
    assert main(["--root", str(root), "journeys", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert agent.TRUST not in out
    assert not marker.exists()
