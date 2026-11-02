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
import ntpath
import os
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_delta_jev import make_renamed

from systemap import cli, git_command, jev, openai_provider, providers
from systemap.cli import main

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


def program_name(executable: Any, argv: Any) -> str:
    """Give the file name of the started program, without the folder.

    On Windows, the audit event can give no executable. Then the first item of the
    arguments is the program. The arguments can be one string on Windows."""
    if executable is None:
        first = argv.split()[0] if isinstance(argv, (str, bytes)) else next(iter(argv), "")
        executable = first
    return ntpath.basename(os.fsdecode(executable)).lower()


def outbound(events: list[tuple[str, tuple[Any, ...]]]) -> list[str]:
    """Give each event that is not a Git process with the no-fetch environment."""
    bad = []
    for event, args in events:
        if event == "subprocess.Popen":
            program = program_name(args[0], args[1])
            env = args[3] or {}
            no_fetch = all(env.get(k) == v for k, v in git_command._NO_FETCH.items())
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


@pytest.fixture(scope="module", params=["jev", "openai"])
def template(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The worst-case repository with current facts, made one time for each provider."""
    root = make_renamed(tmp_path_factory.mktemp(f"template-{request.param}"))
    toml = root / "systemap.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8") + WORST_CASE.format(provider=request.param), "utf-8"
    )
    assert main(["--root", str(root), "extract"]) in (0, 1)
    return root


@pytest.fixture
def worst_case(template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the template for one test, with the two keys in the environment.

    The autouse fixtures in conftest.py remove the keys and the agent permission first."""
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setenv(openai_provider.KEY_ENV, "a test key")
    return Path(shutil.copytree(template, tmp_path / "repo"))


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
