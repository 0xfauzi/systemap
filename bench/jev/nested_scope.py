"""M10 and M2 of the nested parts design: a tree on three levels, and `check --map`.

Acceptance (written before the run, from docs/design/nested-parts.md):

- M10. On the fixture of tests/three_levels.py with the default sizes (11 maps, nested
  maps on levels 1, 2, and 3), `place`, `extract`, `refresh`, `check`, `judgement`, and
  `delta --base HEAD` exit 0. Pass or fail.
- M2. The design gives M2 on the 50-map tree of the fixture big5. big5 is not on this
  host. Thus this script uses a different tree: the fixture of tests/three_levels.py
  with 7 level-1 parts and 3 level-2 parts in each (50 maps on 3 levels). This is not
  the M2 of the design, and its result does not replace that measurement.
  The acceptance is the acceptance of M2: the median wall time of
  `check --map P0/Q0` is at most 0.5 times the median wall time of the full-tree
  `check`, and a syntax error in the model file of the sibling map P1 does not change
  the exit code of `check --map P0/Q0`.

Each command is a new process (`python -m systemap`). The times are wall times of 5
runs. The script uses a new temporary folder, makes a Git repository there for `delta`,
and sends no data out.

Run from the repository root: uv run python bench/jev/nested_scope.py
"""

from __future__ import annotations

import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

import three_levels  # noqa: E402

RUNS = 5


def write(root: Path, parts: int, subs: int) -> None:
    for rel, text in three_levels.files(parts, subs).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def systemap(root: Path, *argv: str) -> tuple[int, float]:
    start = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-m", "systemap", "--root", str(root), *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, time.perf_counter() - start


def git(root: Path, *argv: str) -> None:
    subprocess.run(["git", "-C", str(root), *argv], check=True, capture_output=True)


def m10(base: Path) -> bool:
    root = base / "m10"
    write(root, 2, 2)
    git(root, "init", "-q")
    rows = []
    for argv in (["place"], ["extract"], ["refresh", "--quiet"]):
        rows.append((" ".join(argv), systemap(root, *argv)[0]))
    git(root, "add", "-A")
    git(root, "-c", "user.name=bench", "-c", "user.email=bench@example.com", "commit", "-qm", "m")
    for argv in (["check"], ["judgement"], ["delta", "--base", "HEAD"]):
        rows.append((" ".join(argv), systemap(root, *argv)[0]))
    print(f"M10: {len(three_levels.map_ids(2, 2))} maps")
    for name, code in rows:
        print(f"  {name}: exit {code}")
    ok = all(code == 0 for _name, code in rows)
    print(f"M10: {'pass' if ok else 'fail'}")
    return ok


def m2(base: Path) -> bool:
    root = base / "m2"
    write(root, 7, 3)
    for argv in (["place"], ["extract"], ["refresh", "--quiet"]):
        systemap(root, *argv)
    full = [systemap(root, "check") for _ in range(RUNS)]
    scoped = [systemap(root, "check", "--map", "P0/Q0") for _ in range(RUNS)]
    sibling = root / "map" / three_levels.parts_mod.file_name("P1")
    sibling.write_text(sibling.read_text(encoding="utf-8") + "\nCOMPONENTS = (\n")
    broken_scoped = systemap(root, "check", "--map", "P0/Q0")[0]
    broken_full = systemap(root, "check")[0]
    t_full = statistics.median(t for _c, t in full)
    t_scoped = statistics.median(t for _c, t in scoped)
    ratio = t_scoped / t_full
    print(f"M2 (generated tree, not big5): {len(three_levels.map_ids(7, 3))} maps")
    print(
        f"  full check: exit {sorted({c for c, _t in full})}, times {[round(t, 2) for _c, t in full]}"
    )
    print(
        f"  check --map P0/Q0: exit {sorted({c for c, _t in scoped})}, "
        f"times {[round(t, 2) for _c, t in scoped]}"
    )
    print(f"  median full {t_full:.2f} s, median scoped {t_scoped:.2f} s, ratio {ratio:.2f}")
    print(
        f"  after a syntax error in {sibling.name}: scoped exit {broken_scoped}, full exit {broken_full}"
    )
    same = broken_scoped == scoped[0][0]
    ok = ratio <= 0.5 and same
    print(
        f"M2: {'pass' if ok else 'fail'} (time {'pass' if ratio <= 0.5 else 'fail'}, exit code {'pass' if same else 'fail'})"
    )
    return ok


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        results = [m10(base), m2(base)]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
