"""The history reader caches facts for committed source snapshots.

The cache path is `.systemap/facts/<sha>-<scope>.json`. The scope includes extraction
settings and parser versions, because these can change the facts for the same commit.
The reader does not write to the working tree. The maintainer can delete the cache.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from systemap import delta, extract
from systemap.config import Config

# How much of a diff is read into a question: enough to see what changed.
DIFF_CAP = 20_000


def cache_dir(cfg: Config) -> Path:
    return cfg.root / ".systemap" / "facts"


def facts_at(cfg: Config, sha: str) -> dict[str, Any]:
    """This function reads facts at sha, with a cache for the same extraction inputs."""
    scope = hashlib.sha256(
        f"{cfg!r}|format={extract.FORMAT}|python={sys.version_info[:3]}".encode()
    ).hexdigest()[:16]
    path = cache_dir(cfg) / f"{sha}-{scope}.json"
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


def git(root: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 - git, with arguments this module builds
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise delta.DeltaError(f"git {' '.join(args)}: {done.stderr.strip()[:200]}")
    return done.stdout


def sample(root: Path, since: str, every_days: int, ref: str = "HEAD") -> list[str]:
    """This function selects one commit for each time window, in chronological order.

    The initial commit in each window supplies the sample. Commit activity does not
    change the number of samples.
    """
    lines = git(root, "log", "--first-parent", f"--since={since}", "--format=%H %cI", ref)
    rows = [line.split(" ", 1) for line in lines.splitlines() if " " in line]
    kept: list[str] = []
    last: str | None = None
    for sha, when in reversed(rows):  # oldest first
        day = when[:10]
        if last is None or _days_between(last, day) >= every_days:
            kept.append(sha)
            last = day
    head = git(root, "rev-parse", ref).strip()
    if head and head not in kept:
        kept.append(head)
    return kept


def _days_between(a: str, b: str) -> int:
    from datetime import date

    return abs((date.fromisoformat(b) - date.fromisoformat(a)).days)


def changed_files(root: Path, base: str, head: str) -> list[str]:
    """This function gives changed file paths from Git."""
    out = git(root, "diff", "--name-only", "-z", f"{base}..{head}", "--no-renames")
    return [p for p in out.split("\0") if p]


def diff_of(root: Path, base: str, head: str, paths: list[str], cap: int = DIFF_CAP) -> str:
    """This function gives a selected-file diff between two commits, limited to cap
    characters.
    """
    if not paths:
        return ""
    out = git(root, "diff", "--unified=3", f"{base}..{head}", "--", *paths)
    return out[:cap]
