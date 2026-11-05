"""Measure `check` and `judgement` on a large tree before and after the claim index.

Acceptance values, written before the first run on 2026-11-05:
- With the change, `systemap check` and `systemap judgement` give the same output bytes
  as without it, on the same tree.
- With the change, each command takes at most 0.5 times the seconds without it.

The tree is the M11 tree of the nested parts design (50 maps, about 1,900 modules). The
script needs a tree on which `place` and `extract` ran: `bench/jev/canvas_data_size.py`
of the nested canvas branch writes one. The script runs each command with the code of
two checkouts, `BEFORE` and `AFTER`, and compares the output and the seconds. One run of each command. The host and the load
change the seconds, so the ratio is the result, not the seconds.

Run from the repository root:

    uv run python bench/jev/claim_speed.py BEFORE_CHECKOUT AFTER_CHECKOUT TREE_DIR
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

COMMANDS = ("check", "judgement")


def _run(checkout: Path, root: Path, command: str) -> tuple[bytes, float, int]:
    began = time.perf_counter()
    done = subprocess.run(
        ["uv", "run", "--quiet", "systemap", "--root", str(root), command],
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    return done.stdout + done.stderr, time.perf_counter() - began, done.returncode


def main(before: Path, after: Path, root: Path) -> int:
    if not (root / "systemap.toml").exists():
        print(f"{root} has no systemap.toml. Write the tree first. The measurement did not run.")
        return 2
    ok = True
    for command in COMMANDS:
        old, old_s, old_code = _run(before, root, command)
        new, new_s, new_code = _run(after, root, command)
        same = old == new and old_code == new_code
        ratio = new_s / old_s
        passed = same and ratio <= 0.5
        ok = ok and passed
        print(
            f"{command}: before {old_s:.1f} s, after {new_s:.1f} s, ratio {ratio:.3f}, "
            f"same output {same}: {'PASS' if passed else 'FAIL'}"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
