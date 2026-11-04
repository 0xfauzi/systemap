"""Read committed source trees and models from Git for `systemap delta` and the page.

`facts_at` writes the blobs of a commit into a temporary directory and extracts
facts there. It reads the tree with `git ls-tree` and `git cat-file`, so the files
are the committed blobs. `git archive` is not used, because it applies the
`export-subst` and `export-ignore` attributes: a substituted version string would
be a source change in every commit, and an ignored module would be absent.
The working tree is not read.
"""

from __future__ import annotations

import dataclasses
import io
import os
import subprocess
import tempfile
import threading
import time
import tomllib
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, BinaryIO

from systemap import extraction, git_command, nest, repo_files, tool_table
from systemap.config import CONFIG_FILE, Config, ConfigError
from systemap.delta_link import page_url

# Git tree entry modes that this reader writes.
REGULAR = ("100644", "100755")
SYMLINK = "120000"
# The tree reader writes a blob in parts of this size.
CHUNK = 1 << 20
# If `git cat-file --batch` gives no bytes for this number of seconds, the reader stops it.
BLOB_LIMIT = git_command.TIMEOUT
# The version of the facts at a commit. Version 2 adds `refused_paths`. The facts cache
# scope contains this value, so a cache of version 1 is not read.
TREE_READER = 2


class DeltaError(Exception):
    """The program cannot compare the requested commits. The message gives the reason."""


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return git_command.run(repo, *args, stdin=stdin, timeout=300, error=DeltaError)


def _stderr(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stderr.decode("utf-8", "replace").strip()


def resolve(repo: Path, ref: str) -> str:
    """This function resolves a Git ref to a full commit SHA, or raises DeltaError.

    If Git writes an error, for example because it refuses the repository, the error text
    gives the Git cause.
    """
    proc = _git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    if proc.returncode != 0 or not proc.stdout.strip():
        if _stderr(proc):
            found = git_command.cause(proc.stderr, proc.returncode)
            raise DeltaError(f"Git cannot resolve the ref {ref}. Git gave: {found}")
        raise DeltaError(f"unknown ref {ref}. Give a commit, branch, or tag that Git can resolve.")
    return proc.stdout.decode("utf-8").strip()


def merge_base(repo: Path, base: str, head: str) -> str:
    """This function finds the common ancestor of two refs as a full commit SHA.

    The function resolves the two refs first. Thus Git does not read a ref as an option.
    A ref that Git cannot resolve gives DeltaError. If Git finds no common ancestor, the
    result is DeltaError. The function does not use a different commit as the base.
    """
    base_sha, head_sha = resolve(repo, base), resolve(repo, head)
    proc = _git(repo, "merge-base", base_sha, head_sha)
    out = proc.stdout.decode("utf-8").strip()
    if proc.returncode == 0 and out:
        return out
    detail = f" Git gave: {_stderr(proc)}" if _stderr(proc) else ""
    raise DeltaError(
        f"Git found no common ancestor of {base} and {head}.{detail} Give a base that has "
        "history in common with the head. If the clone is shallow, use git fetch --unshallow."
    )


@dataclasses.dataclass(frozen=True)
class _Entry:
    mode: str
    oid: str
    path: str


def _entries(repo: Path, sha: str) -> list[_Entry]:
    """This function lists the blobs of a commit tree with their modes and paths."""
    proc = _git(repo, "ls-tree", "-r", "-z", "--full-tree", sha)
    if proc.returncode != 0:
        raise DeltaError(f"git ls-tree {sha[:7]} gave an error: {_stderr(proc)}")
    out: list[_Entry] = []
    for record in proc.stdout.split(b"\0"):
        head, tab, raw_path = record.partition(b"\t")
        fields = head.decode("ascii", "replace").split()
        if not tab or len(fields) != 3 or fields[1] != "blob":
            continue
        out.append(_Entry(fields[0], fields[2], raw_path.decode("utf-8", "surrogateescape")))
    return out


class _Blobs:
    """One `git cat-file --batch` process that gives the blobs of a list, in order.

    A thread sends the requests. Thus the process does not stop for each request. The
    caller reads each blob in the order of the list. `copy` writes a blob in parts of
    `CHUNK` bytes. Thus a large blob is not in memory at one time.

    A second thread stops the process if it gives no bytes for `BLOB_LIMIT` seconds.
    Then the reader gives DeltaError with the time limit.
    """

    def __init__(self, repo: Path, oids: list[str]) -> None:
        self._errors = tempfile.TemporaryFile()
        self._proc = subprocess.Popen(
            git_command.command("cat-file", "--batch"),
            cwd=repo,
            env=git_command.env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._errors,
        )
        self._sender = threading.Thread(target=self._send, args=(oids,), daemon=True)
        self._sender.start()
        self._limit, self._progress, self._expired = BLOB_LIMIT, time.monotonic(), False
        self._stopped = threading.Event()
        threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self) -> None:
        """This method stops the process if it gives no bytes in the time limit."""
        while not self._stopped.wait(self._limit / 10):
            if time.monotonic() - self._progress > self._limit:
                self._expired = True
                self._proc.kill()
                return

    def _error(self, problem: str) -> DeltaError:
        """This method gives the error. If the watch thread stopped Git, it gives the limit."""
        if self._expired:
            problem = f"git cat-file did not stop in the time limit of {self._limit:g} s"
        return DeltaError(problem)

    def _send(self, oids: list[str]) -> None:
        stdin = self._proc.stdin
        assert stdin is not None
        try:
            for oid in oids:
                stdin.write(f"{oid}\n".encode("ascii"))
            stdin.close()
        except (OSError, ValueError):
            return  # The reader stopped the process first.

    def __enter__(self) -> _Blobs:
        return self

    def __exit__(self, kind: type[BaseException] | None, *_rest: object) -> None:
        proc = self._proc
        self._stopped.set()
        if kind is not None:
            proc.kill()
        self._sender.join(timeout=60)
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        assert proc.stdout is not None
        proc.stdout.close()
        self._errors.seek(0)
        problem = self._errors.read().decode("utf-8", "replace").strip()
        self._errors.close()
        if kind is None and proc.returncode != 0:
            raise self._error(f"git cat-file gave an error: {problem}")

    def copy(self, out: BinaryIO) -> None:
        """This method writes the next blob to `out` in parts."""
        stdout = self._proc.stdout
        assert stdout is not None
        header = stdout.readline().decode("utf-8", "replace").split()
        self._progress = time.monotonic()
        if len(header) != 3 or header[1] != "blob":
            raise self._error(f"git cat-file gave no blob: {' '.join(header)}")
        left = int(header[2])
        while left:
            part = stdout.read(min(CHUNK, left))
            if not part:
                raise self._error(f"git cat-file stopped before the end of the blob {header[0]}")
            self._progress = time.monotonic()
            out.write(part)
            left -= len(part)
        stdout.read(1)

    def read(self) -> bytes:
        """This method gives the bytes of the next blob."""
        out = io.BytesIO()
        self.copy(out)
        return out.getvalue()


def blobs_at(repo: Path, sha: str, paths: Iterable[str]) -> dict[str, bytes | None]:
    """This function gives the committed bytes of each path at `sha`.

    A path that is not in the tree of `sha` is not in the result. A path whose entry is
    not a regular file, for example a symbolic link, gives None.
    """
    wanted = set(paths)
    entries = [e for e in _entries(repo, sha) if e.path in wanted]
    out: dict[str, bytes | None] = {e.path: None for e in entries}
    regular = [e for e in entries if e.mode in REGULAR]
    with _Blobs(repo, [e.oid for e in regular]) as blobs:
        for entry in regular:
            out[entry.path] = blobs.read()
    return out


class _Inside:
    """This record tells if a resolved target is in `into`. It resolves each folder once.

    A committed link can be a folder in the path of a later entry. Thus the reader
    resolves the folder of each target before it writes.
    """

    def __init__(self, into: Path) -> None:
        self.into, self._folders = into, dict[Path, bool]()

    def __call__(self, target: Path) -> bool:
        folder = target.parent
        if folder not in self._folders:
            self._folders[folder] = repo_files.inside(self.into, folder)
        return self._folders[folder] and not target.is_symlink()


def refusal(rel: str) -> str:
    """This function gives the cause if the tree reader refuses a committed path, or "".

    The rule is the same on each platform. Thus the facts at a commit are the same on
    each platform. A Windows computer reads a backslash as a separator and a colon as a
    drive or a data stream.
    """
    if "\\" in rel:
        return "the path contains a backslash. Windows reads a backslash as a folder separator"
    if ":" in rel:
        return "the path contains a colon. Windows reads a colon as a drive or a data stream"
    parts = rel.split("/")
    if not repo_files.plain(rel) or any(p in ("", ".", "..") for p in parts):
        return "the path is absolute, or it contains an empty, . or .. part"
    if parts[0].lower() == ".git":
        return "the path is in the .git folder"
    return ""


def _link(target: Path, into: Path, value: bytes) -> str:
    """This function makes a symbolic link if it stays inside the tree.

    The result is the cause if the function does not make the link, or "".
    """
    pointed = (target.parent / os.fsdecode(value)).resolve()
    if into not in (pointed, *pointed.parents):
        return "the link goes to a file that is not in the tree"
    try:
        target.symlink_to(os.fsdecode(value))
    except OSError as exc:
        return f"the link could not be made: {type(exc).__name__}"
    return ""


def _plan(
    entries: list[_Entry], into: Path
) -> tuple[list[tuple[_Entry, Path]], list[tuple[str, str]]]:
    """This function gives the entries to write with their targets, and the refused
    paths with their causes."""
    todo: list[tuple[_Entry, Path]] = []
    refused: list[tuple[str, str]] = []
    for entry in entries:
        if entry.mode not in REGULAR and entry.mode != SYMLINK:
            continue
        cause = refusal(entry.path)
        if cause:
            refused.append((entry.path, cause))
        else:
            todo.append((entry, into.joinpath(*entry.path.split("/"))))
    return todo, refused


def write_tree(repo: Path, sha: str, into: Path) -> list[tuple[str, str]]:
    """This function writes the committed blobs of `sha` into `into`.

    The function writes each blob in parts. It does not read a blob whose path `refusal`
    refuses. It does not write a target whose resolved path is not in `into`. The result
    gives each path that the function did not write, with its cause.
    """
    todo, refused = _plan(_entries(repo, sha), into)
    inside = _Inside(into)
    with (
        _Blobs(repo, [entry.oid for entry, _target in todo]) as blobs,
        open(os.devnull, "wb") as nowhere,
    ):
        for entry, target in todo:
            if not inside(target):
                blobs.copy(nowhere)
                refused.append((entry.path, "the resolved path is not in the tree folder"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry.mode == SYMLINK:
                cause = _link(target, into, blobs.read())
                if cause:
                    refused.append((entry.path, cause))
                continue
            with target.open("wb") as out:
                blobs.copy(out)
    return sorted(refused)


def facts_at(cfg: Config, sha: str) -> dict[str, Any]:
    """This function extracts facts at a Git commit without reading the working tree.

    The facts have no record for a path that the tree reader refuses. `refused_paths`
    gives each such path and its cause. Thus a comparison can tell that the changes of
    these paths are not known.
    """
    with tempfile.TemporaryDirectory(prefix="systemap-delta-") as tmp:
        into = Path(tmp).resolve()
        refused = write_tree(cfg.root, sha, into)
        facts = extraction.build(dataclasses.replace(cfg, root=into))
    facts["built_at_commit"] = sha
    facts["refused_paths"] = _records(refused)
    return facts


def page_url_at(cfg: Config, sha: str) -> str:
    """This function reads `[delta] page_url` from the committed configuration at `sha`.

    The delta comment gets its link from the base commit, not from the working tree.
    In CI, the working tree is the pull request, and a fork can change its configuration.
    A commit without the configuration or without the value gives "". An incorrect
    committed configuration gives DeltaError. Its text names the file and the commit.
    """
    blobs = blobs_at(cfg.root, sha, (CONFIG_FILE, "pyproject.toml"))
    raw, where = _committed_table(blobs, sha[:7])
    try:
        return page_url(raw, where)
    except ValueError as exc:
        raise DeltaError(str(exc)) from exc


def comment_page_url(cfg: Config, sha: str) -> tuple[str, list[str]]:
    """Give the link value for the delta comment, and the warning lines.

    An incorrect value at the base commit does not stop the comment. The comment then
    has no link, and the warning gives the cause. Thus a pull request that corrects the
    value also gets its comment."""
    try:
        return page_url_at(cfg, sha), []
    except DeltaError as exc:
        return "", [
            str(exc),
            "The comment does not have a link to the Changes view. "
            "After the merge of a correct value, the comment has the link.",
        ]


def _committed_table(blobs: dict[str, bytes | None], short: str) -> tuple[dict[str, Any], str]:
    """Give the configuration table of the committed files, as `config.read_raw` does.

    The second value names the file of the table and the commit, for an error text."""
    own = blobs.get(CONFIG_FILE)
    if own is not None:
        where = f"{CONFIG_FILE} at {short}"
        return _toml(own, where), where
    where = f"pyproject.toml [tool.systemap] at {short}"
    project = blobs.get("pyproject.toml")
    if project is None:
        return {}, where
    return _toml(project, where, tool_table.section), where


Part = Callable[[dict[str, Any]], dict[str, Any] | None]


def _toml(data: bytes, where: str, part: Part | None = None) -> dict[str, Any]:
    """Read a committed TOML file, and with `part`, one table of it.

    A file that is not UTF-8 TOML, or a `part` that is not a table, gives DeltaError."""
    try:
        table = tomllib.loads(data.decode("utf-8-sig"))
        return (part(table) or {}) if part else table
    except ValueError as exc:
        raise DeltaError(f"{where}: {exc}") from exc


def _records(refused: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"path": path, "reason": cause} for path, cause in refused]


def refused_lines(*facts: dict[str, Any]) -> list[str]:
    """This function gives the text lines for the refused paths of the facts at commits.

    The changes of these paths are not known. The lines are empty if no path is refused.
    """
    found = sorted({(r["path"], r["reason"]) for f in facts for r in f.get("refused_paths", [])})
    if not found:
        return []
    return [
        "Not in this comparison: the tree reader refused these committed paths. "
        "Their changes are not known.",
        *(f"  {path}: {cause}" for path, cause in found),
    ]


def model_at(cfg: Config, sha: str) -> nest.Tree | str:
    """This function loads the map tree from the committed model files at `sha`.

    The model files are Python, as on disk. The configuration on disk gives the model
    path. If the commit has no model that loads, the result is the reason, not a tree.
    """
    with tempfile.TemporaryDirectory(prefix="systemap-model-") as tmp:
        into = Path(tmp).resolve()
        write_tree(cfg.root, sha, into)
        if not (into / cfg.model).is_file():
            return f"{cfg.model} is not in the commit {sha[:7]}"
        try:
            return nest.load(dataclasses.replace(cfg, root=into))
        except ConfigError as exc:
            return f"the model at {sha[:7]} does not load: {exc}"
