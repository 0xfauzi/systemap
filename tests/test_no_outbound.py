"""systemap sends no data out of the computer by default.

Each command operates here with the worst case of a person who did not ask for a request:
- TYPESAFE_API_KEY and OPENAI_API_KEY are set in the environment.
- systemap.toml sets `[jev] enabled = true`, `[decisions] provider` ("jev" and then
  "openai"), and an `[agent]` command. A cloned repository can contain such a file.

The command line gives no `--provider`, `--decide`, or `--order-by-drift`.

A Python audit hook records each socket connection, each name lookup, each urllib request,
and each subprocess. The acceptance values are:
- 0 socket connections, 0 name lookups, and 0 urllib requests.
- 0 subprocesses other than Git.
- Each Git subprocess has the environment that stops a fetch (`git_command.env`).

The test also lists each command of the parser. A new command must be in RUN or in
NOT_RUN. Thus a new command cannot skip this test.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_delta_jev import renamed

from systemap import cli, jev, openai_provider, providers
from systemap.cli import main

__all__ = ["renamed"]

# The events that send data out, or that start a different program.
NETWORK = {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "urllib.Request"}
STARTED: list[tuple[str, tuple[Any, ...]]] = []
WATCHING: list[bool] = []


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if not WATCHING:
        return
    if event in NETWORK or event == "subprocess.Popen":
        STARTED.append((event, args))
    if event in NETWORK:
        # Stop the connection. The test fails on the recorded event.
        raise RuntimeError(f"systemap tried to send data out: {event} {args!r}")


sys.addaudithook(_hook)


@contextlib.contextmanager
def watched() -> Iterator[list[tuple[str, tuple[Any, ...]]]]:
    STARTED.clear()
    WATCHING.append(True)
    try:
        yield STARTED
    finally:
        WATCHING.clear()


def outbound(events: list[tuple[str, tuple[Any, ...]]]) -> list[str]:
    """Give each event that is not a Git process with the no-fetch environment."""
    bad = []
    for event, args in events:
        if event == "subprocess.Popen":
            program = Path(os.fsdecode(args[0])).name
            env = args[3] or {}
            no_fetch = env.get("GIT_ALLOW_PROTOCOL") == "" and env.get("GIT_NO_LAZY_FETCH") == "1"
            if program in {"git", "git.exe"} and no_fetch:
                continue
        bad.append(f"{event}: {args!r}"[:300])
    return bad


# The default command line of each command. Each runs with no option that asks for a request.
RUN: dict[str, tuple[str, ...]] = {
    "init": ("init", "--no-ci"),
    "extract": ("extract",),
    "facts": ("facts",),
    "place": ("place", "--print"),
    "render": ("render",),
    "check": ("check",),
    "figure": ("figure",),
    "refresh": ("refresh",),
    "judgement": ("judgement",),
    "rules": ("rules",),
    "delta": ("delta", "--base", "HEAD~1"),
    "suggest": ("suggest",),
    "describe": ("describe",),
    "history": ("history",),
    "explain": ("explain", "crossing import"),
    "skill": ("skill", "--print"),
    "audit": ("audit",),
    "audit --dry-run": ("audit", "--dry-run"),
    "journeys": ("journeys",),
    "plan": ("plan", "read the input in parts"),
    "triage": ("triage", "the reader fails"),
    "convert": ("convert",),
    "review": ("review", "Reader"),
    "decisions pending": ("decisions", "pending"),
    "decisions status": ("decisions", "status"),
}

# The commands that this test does not operate, with the reason.
NOT_RUN = {
    "serve": "It serves files on 127.0.0.1 until it stops. It does not connect out.",
    "live": "It serves files on 127.0.0.1 until it stops. It does not connect out.",
    "decisions submit": "It reads verdicts from stdin. The decisions tests operate it.",
}

WORST_CASE = """
[jev]
enabled = true

[decisions]
provider = "{provider}"

[agent]
command = "sh -c 'echo started > agent-started.txt'"
"""


def subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def commands() -> set[str]:
    """Give each command of the parser. A command with actions gives each action."""
    names: set[str] = set()
    for name, sub in subcommands(cli.build_parser()).items():
        names.update({f"{name} {x}" for x in subcommands(sub)} or {name})
    return names


def test_each_command_is_listed() -> None:
    listed = {k.split(" --")[0] for k in RUN} | set(NOT_RUN)
    assert commands() - listed == set()


@pytest.fixture(params=["jev", "openai"])
def worst_case(
    renamed: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Path:
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setenv(openai_provider.KEY_ENV, "a test key")
    monkeypatch.delenv("SYSTEMAP_TRUST_AGENT_COMMAND", raising=False)
    toml = renamed / "systemap.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8") + WORST_CASE.format(provider=request.param), "utf-8"
    )
    assert main(["--root", str(renamed), "extract"]) in (0, 1)
    return renamed


@pytest.mark.parametrize("name", list(RUN))
def test_a_command_sends_no_data_by_default(
    name: str, worst_case: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with watched() as events:
        try:
            main(["--root", str(worst_case), *RUN[name]])
        except SystemExit as exc:
            pytest.fail(f"{name}: the command line is not correct: exit {exc.code}")
    out, err = capsys.readouterr()
    assert outbound(events) == [], out + err
    assert not (worst_case / "agent-started.txt").exists()


@pytest.mark.parametrize("name", ["audit", "plan", "triage"])
def test_an_ask_command_without_the_provider_option_says_so(
    name: str, worst_case: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--root", str(worst_case), *RUN[name]]) == 1
    assert f"{name}: {providers.NOT_SELECTED}" in capsys.readouterr().out


def test_the_hook_finds_a_connection() -> None:
    """The control: the hook records a connection attempt and stops it."""
    import socket

    with watched() as events, pytest.raises(RuntimeError, match="send data out"):
        socket.create_connection(("192.0.2.1", 9), timeout=0.01)
    assert outbound(events)
