"""The history reader caches facts for committed source snapshots.

The cache path is `.systemap/facts/<sha>-<scope>.json`. The scope includes extraction
settings and parser versions, because these can change the facts for the same commit.
The reader does not write to the working tree. The maintainer can delete the cache.

A revision from a person goes to `delta.resolve` first. Then the Git commands get only
the full commit SHA after `--end-of-options`. Thus Git does not read a revision as an
option. Each cache writer uses a different temporary file. Thus two processes can write
the same cache file at the same time.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from systemap import delta, delta_git, extraction, file_write
from systemap import language as languages
from systemap.config import Config

# How much of a diff is read into a question: enough to see what changed.
DIFF_CAP = 20_000
# A full commit SHA: SHA-1 or SHA-256.
FULL_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def cache_dir(cfg: Config) -> Path:
    return cfg.root / ".systemap" / "facts"


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
    if path.exists():
        try:
            held: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return held
        except ValueError:
            pass
    facts = delta.facts_at(cfg, sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_write.write_atomic(path, json.dumps(facts))
    return facts


def git(root: Path, *args: str) -> str:
    """This function gives the output of a Git command as UTF-8 text, whatever the locale."""
    done = subprocess.run(  # noqa: S603 - git, with arguments this module builds
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if done.returncode != 0:
        raise delta.DeltaError(f"git {' '.join(args)}: {done.stderr.strip()[:200]}")
    return done.stdout


def sample(root: Path, since: str, every_days: int, ref: str = "HEAD") -> list[str]:
    """This function selects one commit for each time window, in chronological order.

    The initial commit in each window supplies the sample. Commit activity does not
    change the number of samples. The last sample is the ref, if its commit is in the
    range. A commit outside the range is not a sample. A ref that Git cannot resolve to
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
    out = git(root, "diff", "--unified=3", "--end-of-options", f"{base}..{head}", "--", *paths)
    return out[:cap]
