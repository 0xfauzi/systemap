"""W1: the canvas data with the change keys of the Changes view (step 4, `canvas_changes`).

Acceptance values, written before the first run on 2026-11-07:

1. Without change data, the canvas data text (`canvas_data.text`) of the working tree is
   equal, byte for byte, to the text of commit d8ac070 (`canvas_data` from a copy of `src`
   of that commit, `git archive`) for the same tree. The script compares the M11 tree (50
   maps) and the three-level tree of tests/three_levels.py. Pass or fail.
2. C1 with change data: the canvas data text of the M11 tree with a large change is at most
   2 MB (2,097,152 bytes) raw. Pass or fail. The large change: each module of a card on
   level 3 has one more function (819 modules), and in each map on level 3 the first card
   has a changed `does` text. The change data of each map comes from
   `render_pages.page_change` against the base commit, as `systemap render --base` makes
   it, with the working tree as the head.

The script also gives these values. They have no acceptance value: the bytes after gzip -6,
the bytes of the change keys (`ch`, `cm`, `cl`, `cr` and `ci`) of all maps, and the time of
the change data and of one build.

The script writes each tree in a new temporary folder with a new Git repository. It sends
no data out.

Run from the repository root: uv run python bench/jev/canvas_changes_size.py
"""

from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests"))

import canvas_data_size as c1  # noqa: E402
import three_levels  # noqa: E402

from systemap import canvas_data, change, config, facts_file, nest, render_pages  # noqa: E402
from systemap.cli import main as cli  # noqa: E402

BASE = "d8ac070"
RAW_LIMIT = 2_097_152
KEYS = ("ch", "cm", "cl", "cr", "ci")
OLD_TEXT = (
    "import sys; from pathlib import Path; "
    "from systemap import canvas_data, config, facts_file, nest; "
    "cfg = config.load(Path(sys.argv[1])); "
    "facts = facts_file.read_facts(cfg.facts_path, cfg.root); "
    "Path(sys.argv[2]).write_text(canvas_data.text(canvas_data.build(cfg, nest.load(cfg), facts)), "
    "encoding='utf-8')"
)


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _quiet(*argv: str) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return cli(list(argv))


def _made(root: Path, files: dict[str, str]) -> str:
    """Write the tree, run place and extract, and commit it. Give the base commit."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for command in ("place", "extract"):
        if _quiet("--root", str(root), command) != 0:
            raise SystemExit(f"failure: {command} did not exit 0")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return git(root, "rev-parse", "HEAD")


def _old_src(tmp: Path) -> Path:
    old = tmp / "old"
    old.mkdir()
    archive = subprocess.run(
        ["git", "-C", str(ROOT), "archive", BASE, "src"], capture_output=True, check=True
    )
    subprocess.run(["tar", "-x", "-C", str(old)], input=archive.stdout, check=True)
    return old / "src"


def _same(root: Path, old: Path) -> tuple[bool, int]:
    """Compare the text of the working tree with the text of BASE. Give the result and the bytes."""
    cfg = config.load(root)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    new = canvas_data.text(canvas_data.build(cfg, nest.load(cfg), facts)).encode("utf-8")
    out = root.parent / (root.name + "-old.json")
    subprocess.run(
        [sys.executable, "-c", OLD_TEXT, str(root), str(out)],
        env={**os.environ, "PYTHONPATH": str(old)},
        check=True,
    )
    return out.read_bytes() == new, len(new)


def _large_change(root: Path) -> int:
    """Add a function to each module of a card on level 3, and change the `does` text of the
    first card of each map on level 3. Give the count of changed modules."""
    count = 0
    for path in sorted((root / "pkg").rglob("deep/c*.py")):
        path.write_text(
            path.read_text(encoding="utf-8") + "\n\ndef more() -> int:\n    return 0\n",
            encoding="utf-8",
        )
        count += 1
    for path in sorted((root / "map").glob("*_deep.py")):
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace('does="Does one task."', 'does="Does one task again."', 1),
            encoding="utf-8",
        )
    return count


def _changed(root: Path, base: str) -> tuple[dict[str, Any], float, float]:
    """Give the canvas data with the change data, the seconds of the change data, and the
    seconds of the build."""
    if _quiet("--root", str(root), "extract") != 0:
        raise SystemExit("failure: extract did not exit 0")
    cfg = config.load(root)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    began = time.perf_counter()
    source = change.source_change(cfg, base, facts, change.WORKING_TREE)
    of = render_pages.page_change(cfg, facts, base, change.WORKING_TREE, source, {})
    changes = {m.id: of(m) for m in tree.maps}
    middle = time.perf_counter()
    data = canvas_data.build(cfg, tree, facts, changes=changes)
    return data, middle - began, time.perf_counter() - middle


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        old = _old_src(tmp)
        roots = {"M11 tree": tmp / "m11", "three levels": tmp / "levels"}
        files = {"M11 tree": c1.files(), "three levels": three_levels.files()}
        bases = {}
        for tree_name, root in roots.items():
            bases[tree_name] = _made(root, files[tree_name])
            same, size = _same(root, old)
            ok &= same
            print(f"1. {tree_name}, no change data: {size:,} bytes, equal to {BASE}: {same}")
        root = roots["M11 tree"]
        modules = _large_change(root)
        data, change_s, build_s = _changed(root, bases["M11 tree"])
        raw = canvas_data.text(data).encode("utf-8")
        keys = sum(
            len(json.dumps(m[k], separators=(",", ":")))
            for m in data["maps"]
            for k in KEYS
            if k in m
        )
        marked = sum(len(m.get("cm", {})) for m in data["maps"])
        inside = sum(len(m.get("ci", [])) for m in data["maps"])
        passed = len(raw) <= RAW_LIMIT
        ok &= passed
        print(
            f"2. M11 tree, {modules} changed modules: {len(raw):,} bytes raw, "
            f"{len(gzip.compress(raw, compresslevel=6)):,} bytes gzip -6, change keys about "
            f"{keys:,} bytes, {marked} marked cards, {inside} cards changed inside, change data "
            f"{change_s:.1f} s, build {build_s:.1f} s: {'pass' if passed else 'fail'}"
        )
    print("result:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
