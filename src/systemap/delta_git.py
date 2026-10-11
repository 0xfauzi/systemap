"""Read committed source trees and figure links from Git for `systemap delta`.

`facts_at` writes the blobs of a commit into a temporary directory and extracts
facts there. It reads the tree with `git ls-tree` and `git cat-file`, so the files
are the committed blobs. `git archive` is not used, because it applies the
`export-subst` and `export-ignore` attributes: a substituted version string would
be a source change in every commit, and an ignored module would be absent.
The working tree is not read.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import extract, nest
from systemap.config import Config, ConfigError

# Git tree entry modes that this reader writes.
REGULAR = ("100644", "100755")
SYMLINK = "120000"


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
    proc = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if proc.returncode != 0 or not proc.stdout.strip():
        raise DeltaError(f"unknown ref {ref}. Give a commit, branch, or tag that Git can resolve.")
    return proc.stdout.decode("utf-8").strip()


def merge_base(repo: Path, base: str, head: str) -> str:
    """This function finds a common ancestor, or uses the base commit if Git cannot find
    one.
    """
    proc = _git(repo, "merge-base", base, head)
    out = proc.stdout.decode("utf-8").strip()
    return out if proc.returncode == 0 and out else base


@dataclasses.dataclass(frozen=True)
class _Entry:
    mode: str
    oid: str
    path: str


def _entries(repo: Path, sha: str) -> list[_Entry]:
    """This function lists the blobs of a commit tree with their modes and paths."""
    proc = _git(repo, "ls-tree", "-r", "-z", "--full-tree", sha)
    if proc.returncode != 0:
        raise DeltaError(f"git ls-tree {sha[:7]} returned an error: {_stderr(proc)}")
    out: list[_Entry] = []
    for record in proc.stdout.split(b"\0"):
        head, tab, raw_path = record.partition(b"\t")
        fields = head.decode("ascii", "replace").split()
        if not tab or len(fields) != 3 or fields[1] != "blob":
            continue
        out.append(_Entry(fields[0], fields[2], raw_path.decode("utf-8", "surrogateescape")))
    return out


def _contents(repo: Path, oids: list[str]) -> list[bytes]:
    """This function reads blobs with one `git cat-file --batch` process, in order."""
    if not oids:
        return []
    proc = _git(repo, "cat-file", "--batch", stdin="".join(f"{o}\n" for o in oids).encode())
    if proc.returncode != 0:
        raise DeltaError(f"git cat-file returned an error: {_stderr(proc)}")
    data, at, out = proc.stdout, 0, []
    for _oid in oids:
        end = data.index(b"\n", at)
        size = int(data[at:end].split()[2])
        out.append(data[end + 1 : end + 1 + size])
        at = end + 1 + size + 1
    return out


def _safe(into: Path, rel: str) -> Path | None:
    """This function gives the target path of a tree entry, or None if it leaves `into`."""
    parts = PurePosixPath(rel).parts
    if not parts or rel.startswith("/") or any(p in ("", ".", "..") for p in parts):
        return None
    if parts[0].lower() == ".git":
        return None
    return into.joinpath(*parts)


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
    """This function writes the committed blobs of `sha` into `into`."""
    entries = [e for e in _entries(repo, sha) if e.mode in REGULAR or e.mode == SYMLINK]
    for entry, data in zip(entries, _contents(repo, [e.oid for e in entries]), strict=True):
        target = _safe(into, entry.path)
        if target is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry.mode == SYMLINK:
            _link(target, into, data)
        else:
            target.write_bytes(data)


def facts_at(cfg: Config, sha: str) -> dict[str, Any]:
    """This function extracts facts at a Git commit without reading the working tree."""
    with tempfile.TemporaryDirectory(prefix="systemap-delta-") as tmp:
        into = Path(tmp).resolve()
        write_tree(cfg.root, sha, into)
        facts = extract.build(dataclasses.replace(cfg, root=into))
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


def remote_repository(repo: Path) -> str:
    """This function gets owner/name from a GitHub origin remote, or gives an empty string."""
    proc = _git(repo, "remote", "get-url", "origin")
    if proc.returncode != 0:
        return ""
    url = proc.stdout.decode("utf-8", "replace").strip()
    found = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{found.group(1)}/{found.group(2)}" if found else ""


def committed_figure(cfg: Config, sha: str) -> str:
    """This function gives the path of the committed full-map SVG figure, or an empty string."""
    svgs = [f for f in cfg.figures if f.out.endswith(".svg")]
    whole = [f for f in svgs if not f.layer]
    for fig in whole + svgs:
        path = f"{cfg.out_dir}/{fig.out}"
        if _git(cfg.root, "cat-file", "-e", f"{sha}:{path}").returncode == 0:
            return path
    return ""


def figure_url(cfg: Config, sha: str, path: str | None = None) -> str:
    """This function gives a URL for the committed full-map figure, or an empty string.

    A comment must have an absolute URL to show a repository image. Only a GitHub
    origin remote gives one.
    """
    owner = remote_repository(cfg.root)
    found = committed_figure(cfg, sha) if path is None else path
    if not owner or not found:
        return ""
    return f"https://github.com/{owner}/blob/{sha}/{found}?raw=true"
