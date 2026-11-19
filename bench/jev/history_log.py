"""B16: the time of the Git log read of the History view (`history_data.read_log`).

Acceptance values, written before the first run on 2026-11-19. The input is a synthetic
Git repository that `git fast-import` makes in a temporary folder: COMMITS commits that are
not merges, one each hour, and each commit changes 3 of FILES Python files with 10 new
lines in each file. It is not a real repository. The values are the median of RUNS runs:

1. `full`: a read with no cache file (`.systemap/history.json` removed). No limit: the
   value is the reference for the other values.
2. `same`: a read with the cache of the same HEAD. 0.2 s or less.
3. `next`: after one new commit, a read with the cache of the commit before it (the read
   of `OLD..HEAD` only). 0.5 s or less, and 10 % of `full` or less.
4. `days`: a read with no cache file and `history_days = 30` (720 of the commits). Less
   than 50 % of `full`.
5. The size of the cache file after `full` and after `days`. No limit: the record gives it.

Run from the repository root:
    uv run python bench/jev/history_log.py
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from systemap import history_data

COMMITS = 5000
FILES = 200
RUNS = 3
T0 = 1_700_000_000
HOUR = 3600
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def _stream(count: int) -> bytes:
    """A fast-import stream of `count` commits on refs/heads/main."""
    out: list[bytes] = []
    for i in range(count):
        at = T0 + i * HOUR
        msg = b"work"
        out.append(b"commit refs/heads/main\n")
        out.append(f"committer t <t@example.com> {at} +0000\n".encode())
        out.append(f"data {len(msg)}\n".encode() + msg + b"\n")
        for k in range(3):
            n = (i * 3 + k) % FILES
            body = "".join(f"x{i}_{j} = {j}\n" for j in range(10 * (i // FILES + 1)))
            data = body.encode()
            out.append(f"M 100644 inline pkg/m{n}.py\n".encode())
            out.append(f"data {len(data)}\n".encode() + data + b"\n")
    return b"".join(out)


def _repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, env=ENV)
    subprocess.run(
        ["git", "fast-import", "--quiet"], cwd=root, input=_stream(COMMITS), check=True, env=ENV
    )
    subprocess.run(["git", "reset", "-q", "--hard", "main"], cwd=root, check=True, env=ENV)


def _commit(root: Path, i: int) -> None:
    (root / "pkg" / "new.py").write_text(f"N = {i}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=ENV)
    at = f"{T0 + (COMMITS + i) * HOUR} +0000"
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "n"],
        cwd=root,
        check=True,
        env={**ENV, "GIT_AUTHOR_DATE": at, "GIT_COMMITTER_DATE": at},
    )


def _time(before: Callable[[], None], run: Callable[[], object]) -> float:
    before()
    start = time.perf_counter()
    run()
    return time.perf_counter() - start


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "r"
        start = time.perf_counter()
        _repo(root)
        print(f"repository: {COMMITS} commits in {time.perf_counter() - start:.1f} s")
        cache = root / history_data.CACHE

        def drop() -> None:
            cache.unlink(missing_ok=True)

        full = [_time(drop, lambda: history_data.read_log(root)) for _ in range(RUNS)]
        full_size = cache.stat().st_size
        same = [_time(lambda: None, lambda: history_data.read_log(root)) for _ in range(RUNS)]
        nexts = []
        for i in range(RUNS):
            nexts.append(_time(lambda i=i: _commit(root, i), lambda: history_data.read_log(root)))
        days = [_time(drop, lambda: history_data.read_log(root, 30)) for _ in range(RUNS)]
        days_size = cache.stat().st_size
        commits = len(history_data.read_log(root, 30).commits)
    f, s, n, d = (statistics.median(x) for x in (full, same, nexts, days))
    checks = {
        "same <= 0.2 s": s <= 0.2,
        "next <= 0.5 s": n <= 0.5,
        "next <= 10 % of full": n <= 0.1 * f,
        "days < 50 % of full": d < 0.5 * f,
    }
    print(f"full: {f:.3f} s (runs {', '.join(f'{x:.3f}' for x in full)})")
    print(f"same: {s:.3f} s (runs {', '.join(f'{x:.3f}' for x in same)})")
    print(f"next: {n:.3f} s (runs {', '.join(f'{x:.3f}' for x in nexts)})")
    print(f"days: {d:.3f} s (runs {', '.join(f'{x:.3f}' for x in days)}), {commits} commits")
    print(f"cache: {full_size} bytes after full, {days_size} bytes after days")
    for name, ok in checks.items():
        print(f"{name}: {'pass' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
