"""Measure the source comparison of a render with nested maps (Codex result change-20).

`systemap render --base REF` makes the change data of each map with `change.for_page`.
The source comparison does not use the model. Before the change, each call compared all
changed source files again: it read each Git blob and parsed each source file again.

Fixture (the script makes it in a temporary directory): the package `pkg` with 200
modules and one test file for each module. The base commit has the 200 modules. The head
commit adds one function to each module and one test to each test file. The model has
one component that claims `pkg.*`.

The script calls `change.for_page` for each map of a render with K maps, for K = 1 and
K = 5. The five maps use the same model. Thus each call does the same source comparison
as a call for a nested map. With the change, the render gives the source comparison of
the first call to the other calls.

Acceptance (written before the change):

1. The median time for K = 5 is at most 1.5 times the median time for K = 1. Before the
   change, the time must be measured.
2. The peak resident memory rise for K = 5 is at most 1.2 times the value before the
   change.

Each measurement operates in a new Python process. Each value has 3 runs. The script
gives the median.

Operate from the repository root: uv run python bench/jev/change_reuse.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

RUNS = 3
MODULES = 200
MODULE = "def f{n}(x: int) -> int:\n    return x + {n}\n\n\nclass C{n}:\n    pass\n"
ADDED = "\n\ndef g{n}() -> None:\n    return None\n"
TEST = "from pkg.m{n} import f{n}\n\n\ndef test_f{n}() -> None:\n    assert f{n}(0) == {n}\n"
ADDED_TEST = "\n\ndef test_more_{n}() -> None:\n    assert f{n}(1) == {n} + 1\n"
CONFIG = '[package_roots]\n"pkg" = "pkg"\n'
MODEL = """
from systemap import Component, Container, Meaning, Model, Region

CONTAINERS = (Container(id="system", label="SYSTEM", box=(16, 16, 700, 400)),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 640, 320), container="system"),)
COMPONENTS = (
    Component(id="All", does="Does all.", implemented_by=("pkg.*",), region="core", x=60, y=90),
)
MODEL = Model(canvas=(740, 440), containers=CONTAINERS, regions=REGIONS,
              components=COMPONENTS, flows=(), flow_kinds=())
MEANING = Meaning(plain={"All": "all"})
"""

PROBE = """
import json, resource, sys, time
from pathlib import Path
from systemap import change, config, extraction, nest

def peak() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024

cfg = config.load(Path(sys.argv[1]))
maps = int(sys.argv[2])
tree = nest.load(cfg)
facts = extraction.build(cfg)
before = peak()
start = time.perf_counter()
if hasattr(change, "source_change"):
    source = change.source_change(cfg, "HEAD~1", facts, "HEAD")
    found = [change.for_page(cfg, tree.top, "HEAD~1", facts, "HEAD", source) for _ in range(maps)]
else:
    found = [change.for_page(cfg, tree.top, "HEAD~1", facts, "HEAD") for _ in range(maps)]
seconds = time.perf_counter() - start
assert all(len(f["modules"]) == 200 for f in found), [len(f["modules"]) for f in found]
tests = len(found[0]["per_component"]["All"]["surface"]["tests_added"])
print(json.dumps({"seconds": seconds, "rise": peak() - before, "tests": tests}))
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


def fixture(root: Path) -> None:
    for folder in ("pkg", "tests", "map"):
        (root / folder).mkdir(parents=True)
    (root / "pkg/__init__.py").write_text("", encoding="utf-8")
    (root / "systemap.toml").write_text(CONFIG, encoding="utf-8")
    (root / "map/model.py").write_text(MODEL, encoding="utf-8")
    for n in range(MODULES):
        (root / f"pkg/m{n}.py").write_text(MODULE.format(n=n), encoding="utf-8")
        (root / f"tests/test_m{n}.py").write_text(TEST.format(n=n), encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    for n in range(MODULES):
        with (root / f"pkg/m{n}.py").open("a", encoding="utf-8") as out:
            out.write(ADDED.format(n=n))
        with (root / f"tests/test_m{n}.py").open("a", encoding="utf-8") as out:
            out.write(ADDED_TEST.format(n=n))
    git(root, "add", "-A")
    git(root, "commit", "-qm", "head")


def measure(root: Path, maps: int) -> dict[str, float]:
    rows = []
    for _ in range(RUNS):
        done = subprocess.run(
            [sys.executable, "-c", PROBE, str(root), str(maps)],
            capture_output=True,
            text=True,
            check=True,
        )
        rows.append(json.loads(done.stdout))
    return {
        "seconds": statistics.median(r["seconds"] for r in rows),
        "rise_mib": statistics.median(r["rise"] for r in rows) / (1 << 20),
        "tests": rows[0]["tests"],
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="systemap-bench-") as tmp:
        root = Path(tmp)
        fixture(root)
        found = {}
        for maps in (1, 5):
            found[maps] = row = measure(root, maps)
            print(
                f"K = {maps}: median {row['seconds'] * 1000:.0f} ms, peak memory rise "
                f"{row['rise_mib']:.1f} MiB, {row['tests']} tests added, {RUNS} runs"
            )
        ratio = found[5]["seconds"] / found[1]["seconds"]
        print(f"K = 5 over K = 1: {ratio:.2f} ({'passes' if ratio <= 1.5 else 'fails'} at 1.50)")


if __name__ == "__main__":
    main()
