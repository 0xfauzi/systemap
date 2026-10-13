"""The interface that supplies questions to a configured coding agent.

systemap asks the agent to write explanations from source facts.
Set the agent command under `[agent]` in `systemap.toml`.
The command reads its question from stdin and writes its answer to stdout.
For a JSON answer, systemap reads the string in the `result` field.

Every question includes the language policy of the configured writing profile.
The "plain" profile gets the policy without its ASD-STE100 section.
The cache key includes the command, policy, question, and context.
A policy or profile change makes old answers unavailable to new requests.
Without a configured agent, systemap shows facts and the missing configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import IO, Any

from systemap.config import Config
from systemap.jev import Cache

TIMEOUT = 300.0
# The bytes that a command can write to stdout before systemap stops it: prose, not a file.
OUTPUT_CAP = 200_000
LANGUAGE_POLICY = (
    resources.files("systemap").joinpath("skill/references/language.md").read_text(encoding="utf-8")
)
# The policy section that only the "asd-ste100" writing profile uses.
STRICT_SECTION = "## ASD-STE100 profile"
NO_AGENT = (
    "No agent is configured. The output contains facts without an agent explanation. "
    'Set the command under [agent] in systemap.toml, for example command = "claude -p". '
    "Then run the command again."
)


class AgentError(Exception):
    """A failure to start the agent or get its answer."""


def policy(profile: str) -> str:
    """Give the language policy for a writing profile, with the profile at the end.

    The "plain" profile gets the policy without the ASD-STE100 section."""
    text = LANGUAGE_POLICY
    start = text.find(STRICT_SECTION)
    if profile != "asd-ste100" and start >= 0:
        end = text.find("\n## ", start)
        text = text[:start] + (text[end + 1 :] if end >= 0 else "")
    return f"{text.rstrip()}\n\nUse the `{profile}` writing profile for this request."


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


def argv(command: str) -> list[str]:
    """Give the program and the arguments of the configured command, or give AgentError.

    The command uses the quotation rules of a POSIX shell. An unmatched quotation mark
    gives AgentError."""
    try:
        words = shlex.split(command)
    except ValueError as exc:
        raise AgentError(
            f"The agent command {command!r} under [agent] in systemap.toml has an incorrect "
            f"quotation: {exc}. Correct the command. Then run the command again."
        ) from exc
    if not words:
        raise AgentError(NO_AGENT)
    return words


def shell_run(command: str, question: str, cwd: Path, timeout: float) -> str:
    """Operate the configured command with the question on stdin.

    The command can write no more than OUTPUT_CAP bytes to stdout. If it writes more,
    this function stops the command and gives AgentError. Only the end of the stderr
    output stays in memory, for the error message."""
    words = argv(command)
    try:
        proc = subprocess.Popen(  # noqa: S603 - the command is the maintainer's own configuration
            words,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )
    except OSError as exc:
        raise AgentError(f"The agent command could not start: {exc}") from exc
    out = _Reader(proc.stdout, OUTPUT_CAP, keep_end=False)
    err = _Reader(proc.stderr, ERROR_KEEP, keep_end=True)
    try:
        # The question and the answer are UTF-8, whatever the locale.
        _collect(proc, question.encode("utf-8"), out, err, timeout)
    finally:
        _stop(proc, out, err)
    if proc.returncode != 0:
        tail = (err.text() or out.text()).strip()[-300:]
        raise AgentError(f"The agent stopped with exit code {proc.returncode}: {tail}")
    return out.text()


# The end of the stderr output that stays in memory for an error message.
ERROR_KEEP = 4096
CHUNK = 65536


class _Reader(threading.Thread):
    """Read one output stream of the command, with no more than `cap` bytes in memory.

    With `keep_end`, the reader keeps the last `cap` bytes. Without it, the reader stops
    at the first byte after `cap` and sets `over`."""

    def __init__(self, stream: IO[bytes] | None, cap: int, *, keep_end: bool) -> None:
        super().__init__(daemon=True)
        self.stream, self.cap, self.keep_end = stream, cap, keep_end
        self.data = bytearray()
        self.over = False
        self.done = threading.Event()

    def run(self) -> None:
        try:
            self._read()
        except (OSError, ValueError):
            pass  # The stream closed when the command stopped.
        finally:
            self.done.set()

    def _read(self) -> None:
        if self.stream is None:
            return
        fd = self.stream.fileno()
        while chunk := os.read(fd, CHUNK):
            self.data += chunk
            if len(self.data) <= self.cap:
                continue
            if not self.keep_end:
                self.over = True
                return
            del self.data[: len(self.data) - self.cap]

    def text(self) -> str:
        text = self.data.decode("utf-8", errors="replace")
        return text.replace("\r\n", "\n").replace("\r", "\n")


def _feed(stream: IO[bytes] | None, data: bytes) -> None:
    """Write the question to stdin, then close stdin."""
    if stream is None:
        return
    try:
        stream.write(data)
        stream.close()
    except OSError:
        pass  # The command stopped before it read the full question.


def _collect(
    proc: subprocess.Popen[bytes], question: bytes, out: _Reader, err: _Reader, timeout: float
) -> None:
    """Send the question and read the output until the command stops, or give AgentError."""
    deadline = time.monotonic() + timeout
    threading.Thread(target=_feed, args=(proc.stdin, question), daemon=True).start()
    out.start()
    err.start()
    late = AgentError(f"The agent did not answer within {timeout:.0f}s")
    if not out.done.wait(timeout):
        raise late
    if out.over:
        raise AgentError(
            f"The agent wrote more than {OUTPUT_CAP:,} bytes of output. systemap stopped the agent"
        )
    try:
        proc.wait(max(0.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as exc:
        raise late from exc
    err.done.wait(max(0.0, deadline - time.monotonic()))


def _stop(proc: subprocess.Popen[bytes], *readers: _Reader) -> None:
    """Stop the command if it operates. Close each stream that its reader does not use."""
    if proc.poll() is None:
        proc.kill()
    proc.wait()
    for reader in readers:
        if reader.is_alive():
            reader.join(1.0)
        if not reader.is_alive() and reader.stream is not None:
            reader.stream.close()


@dataclass
class Agent:
    """Get an agent answer or a cached answer for the same request."""

    command: str
    root: Path
    cache: Cache
    timeout: float = TIMEOUT
    run_command: Run = shell_run
    usage: Usage = field(default_factory=Usage)
    profile: str = "plain"

    def ask(
        self, question: str, context: Any = None, accept: Callable[[str], bool] | None = None
    ) -> str:
        """Get an answer under the language policy of the writing profile.

        With accept, the cache keeps only an answer that accept accepts. A cached answer
        that accept does not accept is not used, and the agent gets the question again."""
        question = f"{policy(self.profile)}\n\n{question}"
        key = cache_key(self.command, question, context)
        held = self.cache.entries.get(key)
        if isinstance(held, dict) and isinstance(held.get("prose"), str):
            if accept is None or accept(str(held["prose"])):
                self.usage.cached += 1
                return str(held["prose"])
        whole = question if context is None else f"{question}\n\n{json.dumps(context, indent=1)}"
        started = time.monotonic()
        prose = _prose(self.run_command(self.command, whole, self.root, self.timeout))
        self.usage.seconds += time.monotonic() - started
        self.usage.called += 1
        self.usage.command = self.command
        if accept is None or accept(prose):
            self.cache.entries[key] = {"prose": prose}
            self.cache.save()
        return prose


def from_cfg(cfg: Config, run_command: Run | None = None) -> Agent:
    """Get the configured agent. Raise AgentError if no command is configured."""
    if not cfg.agent_command.strip():
        raise AgentError(NO_AGENT)
    argv(cfg.agent_command)
    return Agent(
        command=cfg.agent_command.strip(),
        root=cfg.root,
        cache=Cache(cfg.agent_cache_path, root=cfg.root),
        timeout=cfg.agent_timeout,
        run_command=run_command or shell_run,
        profile=cfg.writing_profile,
    )


def has_agent(cfg: Config) -> bool:
    return bool(cfg.agent_command.strip())
