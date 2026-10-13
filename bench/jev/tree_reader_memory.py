"""Measure the time and the peak memory of `delta_git.facts_at` (Codex result change-14).

The tree reader writes the committed blobs of a commit into a temporary directory. Then
the extraction reads the files there. A large blob outside the package roots is not an
extraction input, but the reader reads it.

Fixtures (the script makes them in a temporary directory):

- `small`: the package `pkg` with 20 modules, and one commit.
- `blob`: the `small` fixture and one file `assets/data.bin` of 256 MiB of random bytes.
- `many`: the package `pkg` with 2000 modules, and one commit.

Acceptance (written before the change):

1. For `blob`, the peak resident memory of one `facts_at` call is at most 64 MiB above
   the peak for `small`. Before the change, this value must be measured.
2. For each fixture, the median time after the change is at most 1.2 times the median
   time before the change.

Each measurement operates in a new Python process, because the peak resident memory of
a process does not decrease. Each fixture has 3 runs. The script gives the median time
and the median increase of the peak resident memory.

Operate from the repository root: uv run python bench/jev/tree_reader_memory.py
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

RUNS = 3
BLOB_MIB = 256
MODULE = "def f{n}(x: int) -> int:\n    return x + {n}\n\n\nclass C{n}:\n    pass\n"
CONFIG = '[package_roots]\n"pkg" = "pkg"\n'

PROBE = """
import json, resource, sys, time
from pathlib import Path
from systemap import config, delta_git

def peak() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024

cfg = config.load(Path(sys.argv[1]))
sha = sys.argv[2]
before = peak()
start = time.perf_counter()
facts = delta_git.facts_at(cfg, sha)
seconds = time.perf_counter() - start
print(json.dumps({"seconds": seconds, "rise": peak() - before, "modules": len(facts["components"])}))
"""


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def fixture(root: Path, modules: int, blob: bool) -> str:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg/__init__.py").write_text("", encoding="utf-8")
    for n in range(modules):
        (root / f"pkg/m{n}.py").write_text(MODULE.format(n=n), encoding="utf-8")
    (root / "systemap.toml").write_text(CONFIG, encoding="utf-8")
    if blob:
        (root / "assets").mkdir()
        with (root / "assets/data.bin").open("wb") as out:
            for _ in range(BLOB_MIB):
                out.write(os.urandom(1 << 20))
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "fixture")
    return git(root, "rev-parse", "HEAD")


def measure(root: Path, sha: str) -> dict[str, float]:
    rows = []
    for _ in range(RUNS):
        done = subprocess.run(
            [sys.executable, "-c", PROBE, str(root), sha],
            capture_output=True,
            text=True,
            check=True,
        )
        rows.append(json.loads(done.stdout))
    return {
        "seconds": statistics.median(r["seconds"] for r in rows),
        "rise_mib": statistics.median(r["rise"] for r in rows) / (1 << 20),
        "modules": rows[0]["modules"],
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="systemap-bench-") as tmp:
        found = {}
        for name, modules, blob in (
            ("small", 20, False),
            ("blob", 20, True),
            ("many", 2000, False),
        ):
            root = Path(tmp) / name
            found[name] = measure(root, fixture(root, modules, blob))
            row = found[name]
            print(
                f"{name}: median {row['seconds'] * 1000:.0f} ms, peak memory rise "
                f"{row['rise_mib']:.1f} MiB, {row['modules']} modules, {RUNS} runs"
            )
        above = found["blob"]["rise_mib"] - found["small"]["rise_mib"]
        verdict = "passes" if above <= 64 else "fails"
        print(f"blob minus small: {above:.1f} MiB ({verdict} at 64 MiB)")


if __name__ == "__main__":
    main()
