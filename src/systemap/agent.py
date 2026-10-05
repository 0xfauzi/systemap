"""The interface that supplies questions to a configured coding agent.

systemap asks the agent to write explanations from source facts.
Set the agent command under `[agent]` in `systemap.toml`.
The command reads its question from stdin and writes its answer to stdout.
For a JSON answer, systemap reads the string in the `result` field.

Every question includes the mandatory ASD-STE100 language policy.
The cache key includes the command, policy, question, and context.
A policy change makes old answers unavailable to new requests.
Without a configured agent, systemap shows facts and the missing configuration.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from systemap.config import Config
from systemap.jev import Cache

TIMEOUT = 300.0
# What a command may write before systemap stops reading it: prose, not a file.
OUTPUT_CAP = 200_000
LANGUAGE_POLICY = (
    resources.files("systemap").joinpath("skill/references/language.md").read_text(encoding="utf-8")
)
NO_AGENT = (
    "No agent is configured. The output contains facts without an agent explanation. "
    'Set the command under [agent] in systemap.toml, for example command = "claude -p". '
    "Then run the command again."
)


class AgentError(Exception):
    """A failure to start the agent or get its answer."""


def cache_key(command: str, question: str, context: Any) -> str:
    blob = json.dumps([command, question, context], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _prose(output: str) -> str:
    """The agent answer from stdout or the JSON `result` field."""
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
    """The count of agent calls, cached answers, and elapsed seconds."""

    called: int = 0
    cached: int = 0
    seconds: float = 0.0
    command: str = ""

    def line(self) -> str:
        return (
            f"agent: {self.called} calls, {self.cached} cached answers. "
            f"{self.seconds:.1f}s. {self.command or 'no agent call'}"
        )


Run = Any  # (command, question, cwd, timeout) -> str; the tests pass their own.


def shell_run(command: str, question: str, cwd: Path, timeout: float) -> str:
    """Execute the configured command with the question on stdin."""
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
        raise AgentError(f"The agent command could not start: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AgentError(f"The agent did not answer within {timeout:.0f}s") from exc
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip()[-300:]
        raise AgentError(f"The agent stopped with exit code {done.returncode}: {tail}")
    return done.stdout[:OUTPUT_CAP]


@dataclass
class Agent:
    """Get an agent answer or a cached answer for the same request."""

    command: str
    root: Path
    cache: Cache
    timeout: float = TIMEOUT
    run_command: Run = shell_run
    usage: Usage = field(default_factory=Usage)

    def ask(self, question: str, context: Any = None) -> str:
        """Get an answer under the mandatory language policy."""
        question = f"{LANGUAGE_POLICY}\n\n{question}"
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
    """Get the configured agent. Raise AgentError if no command is configured."""
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
