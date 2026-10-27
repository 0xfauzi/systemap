"""Run Git with settings that stop the programs that a repository configuration names.

A repository that another person controls can name programs in `.git/config`. Git
runs some of these programs during a read: `core.fsmonitor`, the hooks, an external
diff, a `textconv` program, a filter, and `gpg.program`. Each Git command of systemap
goes through this module. The module adds `SAFE_CONFIG` before the Git command. A
command that compares the working tree also gets `filter.<name>.clean` and the other
filter settings for each filter that the repository configuration defines. Each setting
gets the value of the same filter in the configuration of the user, the system, or the
command line. If these scopes do not define the setting, its value is empty. It also gets
`--ignore-submodules=dirty`. Thus Git does not read the files of a submodule, and does
not start a filter that the configuration of the submodule names. The caller adds
`CONTENT` to a command that gives the content of a diff.

A read can need an object that the repository does not have. If the configuration names
a promisor remote, Git then does a lazy fetch. The fetch can run the upload program of
the remote, an `ext::` URL, an SSH command, or a credential helper. Each Git process of
systemap gets the environment of `env`. That environment stops the lazy fetch and each
transport, and it has priority over `protocol.<name>.allow` in the configuration.

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
# This option stops the status command of Git in each submodule. A submodule has its own
# configuration, and that configuration can name a filter that `_no_filters` does not see.
# A new commit of a submodule is still a change. Changed files in a submodule are not.
# The option on the command line has priority over `submodule.<name>.ignore`.
_NO_SUBMODULE_STATUS = "--ignore-submodules=dirty"
# The configuration scopes that a repository can supply. Git reads the other scopes
# from the files of the user and the system, or from the command line.
_REPOSITORY_SCOPES = ("local", "worktree")
_FILTER_KEYS = ("clean", "smudge", "process")
# These variables stop a lazy fetch. An empty `GIT_ALLOW_PROTOCOL` permits no transport.
# Thus it also stops the fetch in a Git that does not know `GIT_NO_LAZY_FETCH`.
_NO_FETCH = {"GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": ""}


class GitError(Exception):
    """Git did not start, did not stop in the time limit, or gave an error."""


def command(*args: str) -> list[str]:
    """This function gives the full Git command line with `SAFE_CONFIG`."""
    return ["git", *SAFE_CONFIG, *args]


def env() -> dict[str, str]:
    """This function gives the environment of a Git process. It stops each lazy fetch."""
    return {**os.environ, **_NO_FETCH}


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
    the repository configuration, and `--ignore-submodules=dirty` after the first argument.
    Use it only for a command of the diff family that compares the working tree.
    If Git cannot start or does not stop in `timeout` seconds, the result is `error`.
    A Git exit code that is not zero is not an error here. The caller examines it.
    """
    if not worktree:
        return _start(cwd, list(args), stdin, timeout, error)
    line = [args[0], _NO_SUBMODULE_STATUS, *args[1:]]
    return _start(cwd, line, stdin, timeout, error, _no_filters(cwd, error))


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
            line,
            cwd=cwd,
            env=env(),
            input=stdin,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise error(f"git {args[0]} did not stop in the time limit of {timeout:g} s") from exc
    except OSError as exc:
        raise error(f"git could not start: {exc}") from exc


def _no_filters(cwd: Path, error: type[Exception]) -> list[str]:
    """This function gives the settings that stop each filter program of the repository scopes.

    Git runs the `clean` program of a filter when it compares a file of the working tree.
    For each `clean`, `smudge` and `process` setting that a repository scope defines, the
    result gives the value of the same key in the user, the system, or the command scope.
    If these scopes do not define the key, the value is empty, and Git then does not run
    the program of the repository. A filter that only the user or the system configuration
    defines is not changed. If a filter name contains `=`, Git cannot read the setting.
    Then the result is `error`.
    """
    repository, trusted = _filters(cwd, error)
    out: list[str] = []
    for name in sorted(_names(repository)):
        if "=" in name:
            raise error(
                f"the repository configuration has the filter name {name!r}. "
                "systemap cannot stop this filter, because the name contains '='"
            )
        for part in _FILTER_KEYS:
            key = f"filter.{name}.{part}"
            if key in repository:
                out += ["-c", f"{key}={trusted.get(key, '')}"]
        out += ["-c", f"filter.{name}.required={_required(name, repository, trusted)}"]
    return out


def _required(name: str, repository: set[str], trusted: dict[str, str]) -> str:
    """This function gives the `required` value of a filter for the `_no_filters` settings.

    It is the trusted value if Git runs a program of the filter. Otherwise it is `false`,
    because Git gives an error for a required filter without a program.
    """
    if _runs(name, repository, trusted):
        return trusted.get(f"filter.{name}.required", "false")
    return "false"


def stopped_filters(cwd: Path, paths: list[str], error: type[Exception]) -> dict[str, str]:
    """This function gives each path that has a stopped filter, with the filter name.

    A filter is stopped if a repository scope defines it, and the settings of `_no_filters`
    leave it without a `clean` or `process` program. Git then compares the working-tree
    file of such a path without its filter. Thus the comparison can show a change that
    does not exist. One `git check-attr` command gives the filter of each path. If Git
    gives an error, the result is `error`.
    """
    if not paths:
        return {}
    repository, trusted = _filters(cwd, error)
    stopped = {name for name in _names(repository) if not _runs(name, repository, trusted)}
    if not stopped:
        return {}
    data = "".join(f"{path}\0" for path in paths).encode("utf-8", "surrogateescape")
    proc = _start(cwd, ["check-attr", "-z", "--stdin", "filter"], data, SHORT, error)
    if proc.returncode:
        raise error(f"git check-attr gave an error: {cause(proc.stderr, proc.returncode)}")
    fields = proc.stdout.decode("utf-8", "surrogateescape").split("\0")
    return {
        path: value
        for path, value in zip(fields[0::3], fields[2::3], strict=False)
        if value in stopped
    }


def _runs(name: str, repository: set[str], trusted: dict[str, str]) -> bool:
    """This function tells if Git runs a program of the filter with the `_no_filters` settings.

    If the `process` key has a value, Git uses only that key, also if the value is empty.
    Otherwise, Git uses the `clean` key.
    """
    process = f"filter.{name}.process"
    if process in repository or process in trusted:
        return bool(trusted.get(process))
    return bool(trusted.get(f"filter.{name}.clean"))


def _filters(cwd: Path, error: type[Exception]) -> tuple[set[str], dict[str, str]]:
    """This function gives the filter keys of the repository scopes and the trusted settings.

    The trusted settings are the filter settings of the user, the system, and the command
    scopes. Git 2.25 and earlier do not know `--show-scope`. With such a Git, each filter
    key of each scope is a key of a repository scope, and no setting is trusted.
    """
    listing = ["config", "--null", "--get-regexp", r"^filter\."]
    proc = _start(cwd, [*listing[:1], "--show-scope", *listing[1:]], None, SHORT, error)
    if proc.returncode in (0, 1):
        return _repository_keys(proc.stdout), _trusted(proc.stdout)
    return _repository_keys(_start(cwd, listing, None, SHORT, error).stdout, scoped=False), {}


def _trusted(listing: bytes) -> dict[str, str]:
    """This function gives the filter settings of the scopes that a repository cannot supply.

    Git lists the scopes in the sequence system, user, repository, and command. Thus the
    last value of a key is the value that Git uses. A program setting without a value is
    not a program, and the result does not include it. A `required` setting without a
    value is `true`.
    """
    fields = listing.decode("utf-8", "surrogateescape").split("\0")
    found: dict[str, str] = {}
    for scope, record in zip(fields[0::2], fields[1::2], strict=False):
        key, newline, value = record.partition("\n")
        if scope in _REPOSITORY_SCOPES or not (newline or key.endswith(".required")):
            continue
        found[key] = value if newline else "true"
    return found


def _repository_keys(listing: bytes, scoped: bool = True) -> set[str]:
    """This function gives the filter keys of the repository scopes in a listing.

    If `scoped` is true, the listing has a scope and a record for each setting, with NUL
    after each one. Otherwise, the listing has only the records, and each record is in a
    repository scope. A record is the key, a newline, and the value. A key without a
    filter name is not in the result.
    """
    fields = listing.decode("utf-8", "surrogateescape").split("\0")
    pairs = (
        zip(fields[0::2], fields[1::2], strict=False) if scoped else (("local", f) for f in fields)
    )
    keys: set[str] = set()
    for scope, record in pairs:
        key = record.partition("\n")[0]
        if scope in _REPOSITORY_SCOPES and key.count(".") >= 2:
            keys.add(key)
    return keys


def _names(keys: set[str]) -> set[str]:
    """This function gives the filter names of the keys. The name of a key is the part
    between the first and the last dot."""
    return {key[len("filter.") : key.rindex(".")] for key in keys}
