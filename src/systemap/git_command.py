"""Run Git with settings that stop the programs that a repository configuration names.

A repository that another person controls can name programs in `.git/config`. Git
runs some of these programs during a read: `core.fsmonitor`, the hooks, an external
diff, a `textconv` program, a filter, and `gpg.program`. Each Git command of systemap
goes through this module. The module adds `SAFE_CONFIG` before the Git command. A
command that compares the working tree also gets `filter.<name>.clean=` and the other
filter settings for each filter that the repository configuration defines. The caller
adds `CONTENT` to a command that gives the content of a diff.

Each command has a time limit. If Git cannot start or does not stop in the time limit,
the result is the error class of the caller. The error text gives the Git cause.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# These settings stop the programs that Git can start during a read. The null device for
# the hooks folder is `/dev/null` on Linux and macOS, and `nul` on Windows.
SAFE_CONFIG = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    f"core.hooksPath={os.devnull}",
    "-c",
    "log.showSignature=false",
    "-c",
    "diff.external=",
)
# These options stop a textconv program and an external diff in a command that gives
# the content of a diff.
CONTENT = ("--no-textconv", "--no-ext-diff")
# The default time limit of a Git command, in seconds.
TIMEOUT = 300.0
# The time limit of a Git command that reads only the configuration, in seconds.
SHORT = 30.0
# The configuration scopes that a repository can supply. Git reads the other scopes
# from the files of the user and the system, or from the command line.
_REPOSITORY_SCOPES = ("local", "worktree")
_FILTER_KEYS = ("clean", "smudge", "process")


class GitError(Exception):
    """Git did not start, did not stop in the time limit, or gave an error."""


def command(*args: str) -> list[str]:
    """This function gives the full Git command line with `SAFE_CONFIG`."""
    return ["git", *SAFE_CONFIG, *args]


def run(
    cwd: Path,
    *args: str,
    stdin: bytes | None = None,
    timeout: float = TIMEOUT,
    worktree: bool = False,
    error: type[Exception] = GitError,
) -> subprocess.CompletedProcess[bytes]:
    """This function runs Git in `cwd` and gives the completed process.

    If `worktree` is true, the command also gets the settings that stop each filter of
    the repository configuration. Use it for a command that compares the working tree.
    If Git cannot start or does not stop in `timeout` seconds, the result is `error`.
    A Git exit code that is not zero is not an error here. The caller examines it.
    """
    extra = _no_filters(cwd, error) if worktree else []
    return _start(cwd, list(args), stdin, timeout, error, extra)


def text(
    cwd: Path,
    *args: str,
    timeout: float = TIMEOUT,
    worktree: bool = False,
    error: type[Exception] = GitError,
    errors: str = "replace",
) -> str:
    """This function gives the output of a Git command as UTF-8 text, whatever the locale.

    If Git gives an exit code that is not zero, the result is `error` with the Git cause.
    """
    proc = run(cwd, *args, timeout=timeout, worktree=worktree, error=error)
    if proc.returncode:
        raise error(f"git {args[0]} gave an error: {cause(proc.stderr, proc.returncode)}")
    return proc.stdout.decode("utf-8", errors)


def cause(stderr: bytes, code: int) -> str:
    """This function gives the line of the Git error output that tells the cause.

    It is the first line that starts with `fatal:` or `error:`. If no line starts with
    these words, it is the last line that is not empty. If Git wrote no text, it is the
    exit code.
    """
    lines = [line.strip() for line in stderr.decode("utf-8", "replace").splitlines()]
    lines = [line for line in lines if line]
    for line in lines:
        if line.startswith(("fatal:", "error:")):
            return line
    return lines[-1] if lines else f"exit code {code}"


def _start(
    cwd: Path,
    args: list[str],
    stdin: bytes | None,
    timeout: float,
    error: type[Exception],
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    line = command(*(extra or []), *args)
    try:
        return subprocess.run(  # noqa: S603 - git, with arguments that systemap makes
            line, cwd=cwd, input=stdin, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise error(f"git {args[0]} did not stop in the time limit of {timeout:g} s") from exc
    except OSError as exc:
        raise error(f"git could not start: {exc}") from exc


def _no_filters(cwd: Path, error: type[Exception]) -> list[str]:
    """This function gives the settings that stop each filter of the repository scopes.

    Git runs the `clean` program of a filter when it compares a file of the working tree.
    The settings make each program of the filter empty, and Git then does not run it. A
    filter of the user or the system configuration is not changed. If a filter name
    contains `=`, Git cannot read the setting. Then the result is `error`.

    Git 2.25 and earlier do not know `--show-scope`. With such a Git, the function stops
    the filters of all scopes.
    """
    listing = ["config", "--null", "--get-regexp", r"^filter\."]
    proc = _start(cwd, [*listing[:1], "--show-scope", *listing[1:]], None, SHORT, error)
    names = _filter_names(proc.stdout)
    if proc.returncode not in (0, 1):
        names = _filter_names(_start(cwd, listing, None, SHORT, error).stdout, scoped=False)
    out: list[str] = []
    for name in sorted(names):
        if "=" in name:
            raise error(
                f"the repository configuration has the filter name {name!r}. "
                "systemap cannot stop this filter, because the name contains '='"
            )
        for key in _FILTER_KEYS:
            out += ["-c", f"filter.{name}.{key}="]
        out += ["-c", f"filter.{name}.required=false"]
    return out


def _filter_names(listing: bytes, scoped: bool = True) -> set[str]:
    """This function gives the filter names of the repository scopes in a listing.

    If `scoped` is true, the listing has a scope and a record for each setting, with NUL
    after each one. Otherwise, the listing has only the records, and each record is in a
    repository scope. A record is the key, a newline, and the value. The name is the part
    of the key between the first and the last dot.
    """
    fields = listing.decode("utf-8", "surrogateescape").split("\0")
    pairs = (
        zip(fields[0::2], fields[1::2], strict=False) if scoped else (("local", f) for f in fields)
    )
    names: set[str] = set()
    for scope, record in pairs:
        key = record.partition("\n")[0]
        if scope in _REPOSITORY_SCOPES and key.count(".") >= 2:
            names.add(key[len("filter.") : key.rindex(".")])
    return names
