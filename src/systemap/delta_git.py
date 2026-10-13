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
from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO

from systemap import extraction, nest, repo_files
from systemap.config import Config, ConfigError

# Git tree entry modes that this reader writes.
REGULAR = ("100644", "100755")
SYMLINK = "120000"
# The tree reader writes a blob in parts of this size.
CHUNK = 1 << 20


class DeltaError(Exception):
    """The program cannot compare the requested commits. The message gives the reason."""


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=repo, input=stdin, capture_output=True, timeout=300, check=False
    )


def _stderr(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stderr.decode("utf-8", "replace").strip()


def resolve(repo: Path, ref: str) -> str:
    """This function resolves a Git ref to a full commit SHA, or raises DeltaError."""
    proc = _git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    if proc.returncode != 0 or not proc.stdout.strip():
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
    """

    def __init__(self, repo: Path, oids: list[str]) -> None:
        self._errors = tempfile.TemporaryFile()
        self._proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=repo,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._errors,
        )
        self._sender = threading.Thread(target=self._send, args=(oids,), daemon=True)
        self._sender.start()

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
            raise DeltaError(f"git cat-file gave an error: {problem}")

    def copy(self, out: BinaryIO) -> None:
        """This method writes the next blob to `out` in parts."""
        stdout = self._proc.stdout
        assert stdout is not None
        header = stdout.readline().decode("utf-8", "replace").split()
        if len(header) != 3 or header[1] != "blob":
            raise DeltaError(f"git cat-file gave no blob: {' '.join(header)}")
        left = int(header[2])
        while left:
            part = stdout.read(min(CHUNK, left))
            if not part:
                raise DeltaError(f"git cat-file stopped before the end of the blob {header[0]}")
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


def _safe(into: Path, rel: str) -> Path | None:
    """This function gives the target path of a tree entry, or None if it can leave `into`.

    The rule is the same on each platform. Thus the facts at a commit are the same on
    each platform. A Windows computer reads a backslash as a separator and a colon as a
    drive. Thus the function refuses a path with a backslash or a colon. `repo_files.plain`
    refuses an absolute path and a `..` part.
    """
    if "\\" in rel or ":" in rel or not repo_files.plain(rel):
        return None
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts) or parts[0].lower() == ".git":
        return None
    return into.joinpath(*parts)


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


def _link(target: Path, into: Path, value: bytes) -> None:
    """This function makes a symbolic link if it stays inside the tree."""
    pointed = (target.parent / os.fsdecode(value)).resolve()
    if into not in (pointed, *pointed.parents):
        return
    try:
        target.symlink_to(os.fsdecode(value))
    except OSError:
        return


def write_tree(repo: Path, sha: str, into: Path) -> None:
    """This function writes the committed blobs of `sha` into `into`.

    The function writes each blob in parts. It does not read a blob whose path `_safe`
    refuses. It does not write a target whose resolved path is not in `into`.
    """
    todo = [
        (entry, target)
        for entry in _entries(repo, sha)
        if entry.mode in REGULAR or entry.mode == SYMLINK
        for target in [_safe(into, entry.path)]
        if target is not None
    ]
    inside = _Inside(into)
    with (
        _Blobs(repo, [entry.oid for entry, _target in todo]) as blobs,
        open(os.devnull, "wb") as nowhere,
    ):
        for entry, target in todo:
            if not inside(target):
                blobs.copy(nowhere)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry.mode == SYMLINK:
                _link(target, into, blobs.read())
                continue
            with target.open("wb") as out:
                blobs.copy(out)


def facts_at(cfg: Config, sha: str) -> dict[str, Any]:
    """This function extracts facts at a Git commit without reading the working tree."""
    with tempfile.TemporaryDirectory(prefix="systemap-delta-") as tmp:
        into = Path(tmp).resolve()
        write_tree(cfg.root, sha, into)
        facts = extraction.build(dataclasses.replace(cfg, root=into))
    facts["built_at_commit"] = sha
    return facts


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
