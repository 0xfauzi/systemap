"""The history reader caches facts for committed source snapshots.

The cache path is `.systemap/facts/<sha>-<scope>.json`. The scope includes extraction
settings and parser versions, because these can change the facts for the same commit.
The reader does not write to the working tree. The maintainer can delete the cache.

A revision from a person goes to `delta.resolve` first. Then the Git commands get only
the full commit SHA after `--end-of-options`. Thus Git does not read a revision as an
option. Each cache writer uses a different temporary file. Thus two processes can write
the same cache file at the same time. Each read and each write of a cache file holds the
lock `.systemap/facts/facts.lock`.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from systemap import delta, delta_git, extraction, file_write, git_command, repo_files
from systemap import language as languages
from systemap.config import Config

# How much of a diff is read into a question: enough to see what changed.
DIFF_CAP = 20_000
# A full commit SHA: SHA-1 or SHA-256.
FULL_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# The time limit of a Git command of this module, in seconds.
TIMEOUT = git_command.TIMEOUT


def cache_dir(cfg: Config) -> Path:
    return cfg.root / ".systemap" / "facts"


def lock_of(cfg: Config) -> Path:
    """This function gives the path for `file_write.locked` for the facts cache.

    The lock file is `.systemap/facts/facts.lock`."""
    return cache_dir(cfg) / "facts"


def cache_scope(cfg: Config, parser: str) -> str:
    """This function gives the cache scope for the extraction settings and the parser.

    The language adapter gives the parser version. A change of the parser version gives
    a different scope, because the parser can change the facts for the same commit."""
    key = f"{cfg!r}|format={extraction.FORMAT}|tree={delta_git.TREE_READER}|parser={parser}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def facts_at(cfg: Config, sha: str) -> dict[str, Any]:
    """This function reads facts at sha, with a cache for the same extraction inputs.

    The sha must be a full commit SHA. A different value gives DeltaError, because a Git
    ref such as HEAD can move, and the cache file name contains the value."""
    if not FULL_SHA.fullmatch(sha):
        raise delta.DeltaError(
            f"The facts cache accepts only a full commit SHA. {sha} is not a full commit SHA."
        )
    scope = cache_scope(cfg, languages.repository(cfg.language).parser_version())
    path = cache_dir(cfg) / f"{sha}-{scope}.json"
    held = _cached(cfg, path)
    if held is not None:
        return held
    facts = delta.facts_at(cfg, sha)
    with file_write.locked(cfg.root, lock_of(cfg)):
        file_write.write_atomic(cfg.root, path, json.dumps(facts))
    return facts


def _cached(cfg: Config, path: Path) -> dict[str, Any] | None:
    """This function gives the cached facts in path, or None if the file is not usable.

    A JSON value that is not a table with a `components` table is not usable.

    The read holds the lock of the facts cache. On Windows, a read cannot occur while a
    different process replaces the file. A link out of the repository (at the file or at a
    folder), a FIFO, and a device give `file_write.RefusedFile` with the cause. They are
    not a missing file."""
    file_write.confined(cfg.root, path)
    if not repo_files.present(path):
        return None
    with file_write.locked(cfg.root, lock_of(cfg)):
        text = file_write.read_text(cfg.root, path)
        if text is None:
            return None
        try:
            held = json.loads(text)
        except ValueError:
            return None
    # A cache file that is not a facts table is not usable. The caller extracts again.
    if not isinstance(held, dict) or not isinstance(held.get("components"), dict):
        return None
    return held


def git(root: Path, *args: str, worktree: bool = False) -> str:
    """This function gives the output of a Git command as UTF-8 text, whatever the locale.

    The command goes through `git_command`, with the time limit `TIMEOUT`. Set `worktree`
    for a command that compares the working tree. A Git error, a Git program that cannot
    start, and a command that does not stop in the time limit give DeltaError.
    """
    done = git_command.run(root, *args, timeout=TIMEOUT, worktree=worktree, error=delta.DeltaError)
    if done.returncode != 0:
        found = git_command.cause(done.stderr, done.returncode)
        raise delta.DeltaError(f"git {' '.join(args)}: {found[:200]}")
    # Universal newlines, as in the text mode of `subprocess.run`.
    out = done.stdout.decode("utf-8", "replace")
    return out.replace("\r\n", "\n").replace("\r", "\n")


def sample(root: Path, since: str, every_days: int, ref: str = "HEAD") -> list[str]:
    """This function selects commits from the first-parent history, in chronological order.

    The oldest commit in the range is the first sample. Each next sample is the first
    commit with a commit date that is `every_days` or more days after the date of the
    previous sample. Thus an interval starts at a commit, not at a fixed date. Many
    commits in one interval give one sample. A period without commits gives no sample. Thus commit
    activity changes the number of samples. The last sample is the ref, if its commit is
    in the range. A commit outside the range is not a sample. A ref that Git cannot resolve to
    a commit gives DeltaError.
    """
    head = delta.resolve(root, ref)
    lines = git(
        root,
        "log",
        "--first-parent",
        f"--since={since}",
        "--format=%H %cI",
        "--end-of-options",
        head,
    )
    rows = [line.split(" ", 1) for line in lines.splitlines() if " " in line]
    kept: list[str] = []
    last: str | None = None
    for sha, when in reversed(rows):  # oldest first
        day = when[:10]
        if last is None or _days_between(last, day) >= every_days:
            kept.append(sha)
            last = day
    if head in {sha for sha, _when in rows} - set(kept):
        kept.append(head)
    return kept


def shallow_note(root: Path, shas: list[str]) -> list[str]:
    """Tell the reader that the samples start at the boundary of a shallow clone.

    A shallow clone has no commits before its boundary commits. Git lists them in the
    `shallow` file. If the oldest sample is a boundary commit, the time range starts
    before the available history. Then the note gives that commit and its date.
    """
    if not shas:
        return []
    path = Path(git(root, "rev-parse", "--git-path", "shallow").strip())
    path = path if path.is_absolute() else root / path
    try:
        boundary = set(path.read_text(encoding="utf-8").split())
    except OSError:
        return []
    if shas[0] not in boundary:
        return []
    day = git(root, "log", "-1", "--format=%cs", "--end-of-options", shas[0]).strip()
    return [
        f"history: This repository is a shallow clone. Its history starts at the shallow "
        f"boundary, commit {shas[0][:12]} on {day}."
    ]


def too_few(count: int, since: str) -> str:
    """This function tells the reader that the range has too few commits for a trend."""
    noun = "commit" if count == 1 else "commits"
    verb = "is" if count == 1 else "are"
    return f"history: There {verb} only {count} {noun} since {since}. Use a longer time range."


def _days_between(a: str, b: str) -> int:
    from datetime import date

    return abs((date.fromisoformat(b) - date.fromisoformat(a)).days)


def changed_files(root: Path, base: str, head: str) -> list[str]:
    """This function gives changed file paths from Git."""
    out = git(
        root, "diff", "--name-only", "-z", "--no-renames", "--end-of-options", f"{base}..{head}"
    )
    return [p for p in out.split("\0") if p]


def diff_of(root: Path, base: str, head: str, paths: list[str], cap: int = DIFF_CAP) -> str:
    """This function gives a selected-file diff between two commits, limited to cap
    characters.
    """
    if not paths:
        return ""
    out = git(
        root,
        "diff",
        *git_command.CONTENT,
        "--unified=3",
        "--end-of-options",
        f"{base}..{head}",
        "--",
        *paths,
    )
    return out[:cap]
