"""The tree at another commit, read once and kept.

Several commands ask what the code looked like somewhere else in history:
`delta` at the base of a branch, the ripple of a change, the trend of a
system over a year. Reading it is expensive, because the facts at a commit
are a whole extraction of that tree, so this module keeps what it read:

    .systemap/facts/<sha>.json

A commit never changes, so a cached answer is never stale and the second
run over the same commit is free. The directory is the maintainer's to
delete; nothing here ever writes into the working copy.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from systemap import delta
from systemap.config import Config

# How much of a diff is read into a question: enough to see what changed.
DIFF_CAP = 20_000


def cache_dir(cfg: Config) -> Path:
    return cfg.root / ".systemap" / "facts"


def facts_at(cfg: Config, sha: str) -> dict[str, Any]:
    """The facts at `sha`, from the cache when they were read before."""
    path = cache_dir(cfg) / f"{sha}.json"
    if path.exists():
        try:
            held: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return held
        except ValueError:
            pass
    facts = delta.facts_at(cfg, sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(facts), encoding="utf-8")
    tmp.replace(path)
    return facts


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 - git, with arguments this module builds
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise delta.DeltaError(f"git {' '.join(args)}: {done.stderr.strip()[:200]}")
    return done.stdout


def sample(root: Path, since: str, every_days: int, ref: str = "HEAD") -> list[str]:
    """One commit every `every_days` days back to `since`, oldest first.

    The first commit of each window is taken, so a busy week and a quiet one
    weigh the same: the question is what the system looked like then, not how
    many commits it took to get there.
    """
    lines = _git(root, "log", "--first-parent", f"--since={since}", "--format=%H %cI", ref)
    rows = [line.split(" ", 1) for line in lines.splitlines() if " " in line]
    kept: list[str] = []
    last: str | None = None
    for sha, when in reversed(rows):  # oldest first
        day = when[:10]
        if last is None or _days_between(last, day) >= every_days:
            kept.append(sha)
            last = day
    head = _git(root, "rev-parse", ref).strip()
    if head and head not in kept:
        kept.append(head)
    return kept


def _days_between(a: str, b: str) -> int:
    from datetime import date

    return abs((date.fromisoformat(b) - date.fromisoformat(a)).days)


def changed_files(root: Path, base: str, head: str) -> list[str]:
    """The files the change touched, paths as git prints them."""
    out = _git(root, "diff", "--name-only", "-z", f"{base}..{head}", "--no-renames")
    return [p for p in out.split("\0") if p]


def diff_of(root: Path, base: str, head: str, paths: list[str], cap: int = DIFF_CAP) -> str:
    """The diff of some files between two commits, cut to `cap` characters."""
    if not paths:
        return ""
    out = _git(root, "diff", "--unified=3", f"{base}..{head}", "--", *paths)
    return out[:cap]
