"""The one door to a coding agent: a question and the structure, prose back.

Some of what systemap has to say is prose that only a reader of the code can
write: what a change means for a journey, what a trend over a year amounts
to. systemap works out the structure itself and asks an agent to put it into
words, the way it asks Jev for a judgement.

The agent is a command you name, so systemap depends on none in particular:

    [agent]
    command = "claude -p"

It is run with the question on stdin and the repository as its directory;
what it writes on stdout is the prose. A command that answers in JSON (for
example `claude -p --output-format json`) is understood too: the `result`
field is taken.

Nothing runs unless a command is set. When none is, the command that wanted
prose prints its structure and says what is missing, and no command fails
for the want of an agent: prose is never a gate.

Every answer is cached on disk (`[agent] cache`), keyed by the command, the
question and the structure, so a second run over an unchanged map costs
nothing and a report can be printed again for free.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap.config import Config
from systemap.jev import Cache

TIMEOUT = 300.0
# What a command may write before systemap stops reading it: prose, not a file.
OUTPUT_CAP = 200_000
NO_AGENT = (
    "no agent is set, so this is the structure without the prose. "
    'Name one under [agent] in systemap.toml, for example command = "claude -p", '
    "and the same report comes back written out."
)


class AgentError(Exception):
    """The agent could not be run, or it failed; the message says which."""


def cache_key(command: str, question: str, context: Any) -> str:
    blob = json.dumps([command, question, context], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _prose(output: str) -> str:
    """The prose the agent wrote: its stdout, or the `result` of a JSON answer."""
    text = output.strip()
    if not text.startswith("{"):
        return text
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
        return str(parsed["result"]).strip()
    return text


@dataclass
class Usage:
    """What a run cost: agent calls, answers from the cache, seconds spent."""

    called: int = 0
    cached: int = 0
    seconds: float = 0.0
    command: str = ""

    def line(self) -> str:
        return (
            f"agent: {self.called} run, {self.cached} from the cache; "
            f"{self.seconds:.1f}s; {self.command or 'no agent called'}"
        )


Run = Any  # (command, question, cwd, timeout) -> str; the tests pass their own.


def shell_run(command: str, question: str, cwd: Path, timeout: float) -> str:
    """The real transport: the command, with the question on stdin."""
    try:
        done = subprocess.run(  # noqa: S603 - the command is the maintainer's own configuration
            shlex.split(command),
            input=question,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AgentError(f"the agent command could not be run: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AgentError(f"the agent did not answer within {timeout:.0f}s") from exc
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip()[-300:]
        raise AgentError(f"the agent exited {done.returncode}: {tail}")
    return done.stdout[:OUTPUT_CAP]


@dataclass
class Agent:
    """Ask one agent for prose, from the cache when it can."""

    command: str
    root: Path
    cache: Cache
    timeout: float = TIMEOUT
    run_command: Run = shell_run
    usage: Usage = field(default_factory=Usage)

    def ask(self, question: str, context: Any = None) -> str:
        """The prose for this question, run once and remembered."""
        key = cache_key(self.command, question, context)
        held = self.cache.entries.get(key)
        if isinstance(held, dict) and isinstance(held.get("prose"), str):
            self.usage.cached += 1
            return str(held["prose"])
        whole = question if context is None else f"{question}\n\n{json.dumps(context, indent=1)}"
        started = time.monotonic()
        prose = _prose(self.run_command(self.command, whole, self.root, self.timeout))
        self.usage.seconds += time.monotonic() - started
        self.usage.called += 1
        self.usage.command = self.command
        self.cache.entries[key] = {"prose": prose}
        self.cache.save()
        return prose


def from_cfg(cfg: Config, run_command: Run | None = None) -> Agent:
    """The agent this project names. Raises AgentError when it names none."""
    if not cfg.agent_command.strip():
        raise AgentError(NO_AGENT)
    return Agent(
        command=cfg.agent_command.strip(),
        root=cfg.root,
        cache=Cache(cfg.agent_cache_path),
        timeout=cfg.agent_timeout,
        run_command=run_command or shell_run,
    )


def has_agent(cfg: Config) -> bool:
    return bool(cfg.agent_command.strip())
