"""Q1: the bytes of the sequence data (`sq`) in the canvas data (step 4, part sequences).

Acceptance values, written before the first run on 2026-11-07, from the task of the part
sequences of step 4 of docs/design/nested-canvas.md:

1. A tree without sequences: the canvas data of the M11 tree (`canvas_data_size.files`, 50
   maps, no sequence) of the work tree has the same bytes as the canvas data of commit BASE
   (d8ac070). C1 stays: at most 2 MB (2,097,152 bytes) raw.
2. The self-map (16 sequences, 69 steps): the canvas data of the work tree, less the keys
   `sq`, has the same bytes as the canvas data of BASE. The increase is at most 20,000 bytes
   raw.
3. A generated tree with sequences: the M11 tree with one sequence of 20 steps in each map
   (50 sequences, 1,000 steps). The canvas data is at most 2 MB raw. The increase over the
   same tree without sequences is information only.

The bytes are the UTF-8 bytes of `canvas_data.text`. The gzip -6 bytes are information
only. The data of BASE comes from `git archive` of `src` at BASE in a new process with that
`src` first on the Python path. The script sends no data out. The values do not depend on
the host load, so the script makes no quiet gate.

Run from the repository root: uv run python bench/jev/canvas_sequences_size.py
"""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import canvas_data_size as size  # noqa: E402

from systemap import canvas_data, config, facts_file, nest  # noqa: E402
from systemap.cli import main  # noqa: E402

BASE = "d8ac070"
SELF_LIMIT = 20_000
STEPS = 20
BUILD = (
    "import sys; from pathlib import Path; "
    "from systemap import canvas_data, config, facts_file, nest; "
    "cfg = config.load(Path(sys.argv[1])); "
    "facts = facts_file.read_facts(cfg.facts_path, cfg.root); "
    "Path(sys.argv[2]).write_text(canvas_data.text(canvas_data.build(cfg, nest.load(cfg), facts)), "
    "encoding='utf-8')"
)


def _sequence(text: str) -> str:
    """Add one sequence of STEPS steps along the chain of flows of a map file of M11."""
    head, meaning = text.split("MEANING = Meaning(", 1)
    flows = [line for line in head.splitlines() if line.startswith("    Flow(")]
    pairs = [(line.split('"')[1], line.split('"')[3]) for line in flows]
    steps = "".join(
        f'Step(acts=("{a}",), measures=(), edge=("{a}", "{b}"), '
        f'say="Step {k + 1}: {a} sends the record to {b}."), '
        for k, (a, b) in enumerate(pairs[:STEPS])
    )
    journey = f'journeys=(Journey(id="walk", label="Walk the records", steps=({steps})),), '
    head = head.replace(
        "from systemap import Component, Container, Flow, Meaning, Model, Region",
        "from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step",
    )
    return head + "MEANING = Meaning(" + journey + meaning


def _tree(root: Path, sequences: bool) -> None:
    for rel, text in size.files().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if sequences and rel.startswith("map/"):
            text = _sequence(text)
        path.write_text(text, encoding="utf-8")
    for command in ("place", "extract"):
        if main(["--root", str(root), command]) != 0:
            raise RuntimeError(f"{command} did not exit 0 in {root}")


def _head(root: Path) -> str:
    cfg = config.load(root)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    return canvas_data.text(canvas_data.build(cfg, nest.load(cfg), facts))


def _base(old: Path, root: Path, out: Path) -> str:
    subprocess.run(
        [sys.executable, "-c", BUILD, str(root), str(out)],
        env={**os.environ, "PYTHONPATH": str(old / "src")},
        check=True,
        cwd=str(out.parent),
    )
    return out.read_text(encoding="utf-8")


def _without(text: str) -> str:
    data: dict[str, Any] = json.loads(text)
    data["maps"] = [{k: v for k, v in m.items() if k != "sq"} for m in data["maps"]]
    return canvas_data.text(data)


def _bytes(text: str) -> tuple[int, int]:
    raw = text.encode("utf-8")
    return len(raw), len(gzip.compress(raw, compresslevel=6))


def main_run() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        old = tmp / "old"
        old.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(ROOT), "archive", BASE, "src"], capture_output=True, check=True
        )
        subprocess.run(["tar", "-x", "-C", str(old)], input=archive.stdout, check=True)
        print(
            "| Tree | Maps | Sequences / steps | BASE raw | Work tree raw | Increase | gzip -6 | Result |"
        )
        print("|---|---|---|---|---|---|---|---|")
        m11 = tmp / "m11"
        _tree(m11, False)
        head, base = _head(m11), _base(old, m11, tmp / "m11.json")
        good = head == base and _bytes(head)[0] <= size.RAW_LIMIT
        ok &= good
        print(
            f"| M11 tree | 50 | 0 / 0 | {_bytes(base)[0]:,} | {_bytes(head)[0]:,} | "
            f"{_bytes(head)[0] - _bytes(base)[0]:+,} | {_bytes(head)[1]:,} | "
            f"{'pass' if good else 'fail'} (same bytes: {head == base}) |"
        )
        own, own_base = _head(ROOT), _base(old, ROOT, tmp / "self.json")
        sq = json.loads(own)["maps"][0].get("sq", [])
        grow = _bytes(own)[0] - _bytes(own_base)[0]
        good = _without(own) == own_base and grow <= SELF_LIMIT
        ok &= good
        print(
            f"| self-map | 1 | {len(sq)} / {sum(len(j['s']) for j in sq)} | {_bytes(own_base)[0]:,} | "
            f"{_bytes(own)[0]:,} | {grow:+,} | {_bytes(own)[1]:,} | "
            f"{'pass' if good else 'fail'} (same bytes less sq: {_without(own) == own_base}) |"
        )
        walked = tmp / "walked"
        _tree(walked, True)
        text = _head(walked)
        maps = json.loads(text)["maps"]
        count = sum(len(m.get("sq", [])) for m in maps)
        steps = sum(len(j["s"]) for m in maps for j in m.get("sq", []))
        good = _bytes(text)[0] <= size.RAW_LIMIT
        ok &= good
        print(
            f"| M11 tree with a sequence in each map | {len(maps)} | {count} / {steps} | "
            f"{_bytes(head)[0]:,} (no sequence) | {_bytes(text)[0]:,} | "
            f"{_bytes(text)[0] - _bytes(head)[0]:+,} | {_bytes(text)[1]:,} | "
            f"{'pass' if good else 'fail'} |"
        )
    print("result:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main_run())
