"""M3 and M4 of the nested parts design: the cost of `systemap parts`, and the size of one
nested model.

Acceptance (written before the run, from docs/design/nested-parts.md):

- M3. The design gives M3 on the fixture big5 (about 4,250 modules). big5 is not on this
  host. Thus this script uses a different tree: the fixture of tests/three_levels.py
  with 7 level-1 parts and 3 level-2 parts in each (50 maps on 3 levels). This is not
  the M3 of the design, and its result does not replace that measurement.
  The acceptance is the acceptance of M3: `systemap parts --json` takes at most 10 s
  (the median wall time of 5 runs), its peak RSS is at most 50 MB above the peak RSS of a
  process that only loads the tree and reads the facts, and its output is at most 50 MB.
- M4. A nested model with 40 components, flows, sequences, and positions is at most
  256 KB and 50,000 values (50 percent of the limits in model_load.py). If not, `parts`
  must use a lower component limit.
  The script makes this model from the self-map of this repository (map/model.py and
  the files that it imports). Each generated component, flow, and sequence step gets the
  mean text length and the mean count of claims and source records of the self-map.
  The numbers of flows and sequences for each component are the ratios of the self-map.
  The value count is the count of the model reader (model_load), one for each value.

Each command of M3 is a new process (`python -m systemap`). The script uses a new
temporary folder and sends no data out.

Run from the repository root: uv run python bench/jev/parts_plan.py
"""

from __future__ import annotations

import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

import three_levels  # noqa: E402

from systemap import config, model_convert, model_load, nest  # noqa: E402
from systemap.model import (  # noqa: E402
    Component,
    Container,
    Flow,
    Journey,
    Meaning,
    Model,
    Region,
    Step,
)

RUNS = 5
CARDS = 40
MAX_BYTES = 256 * 1024
MAX_VALUES = 50_000
LOAD_ONLY = (
    "import resource, sys\n"
    "from pathlib import Path\n"
    "from systemap import config, facts_file, nest\n"
    "cfg = config.load(Path(sys.argv[1]))\n"
    "nest.load(cfg)\n"
    "facts_file.read_facts(cfg.facts_path, cfg.root)\n"
    "print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)\n"
)
PEAK = (
    "import resource, runpy, sys\n"
    "sys.argv = ['systemap', *sys.argv[1:]]\n"
    "try:\n"
    "    runpy.run_module('systemap', run_name='__main__')\n"
    "except SystemExit as exc:\n"
    "    code = exc.code\n"
    "print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, file=sys.stderr)\n"
)


def write(root: Path, parts: int, subs: int) -> None:
    for rel, text in three_levels.files(parts, subs).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def systemap(root: Path, *argv: str) -> tuple[int, float, str]:
    start = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-m", "systemap", "--root", str(root), *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, time.perf_counter() - start, done.stdout


def peak_kb(*argv: str, script: str) -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, "-c", script, *argv], capture_output=True, text=True, check=False
    )
    lines = (done.stderr if script is PEAK else done.stdout).strip().splitlines()
    return int(lines[-1]), done.stdout


def m3(base: Path) -> bool:
    root = base / "m3"
    write(root, 7, 3)
    for argv in (["place"], ["extract"], ["refresh", "--quiet"]):
        systemap(root, *argv)
    runs = [systemap(root, "parts", "--json") for _ in range(RUNS)]
    median = statistics.median(t for _c, t, _out in runs)
    out_bytes = len(runs[0][2].encode("utf-8"))
    plan_bytes = (root / "map/parts/plan.json").stat().st_size
    load_kb, _ = peak_kb(str(root), script=LOAD_ONLY)
    parts_kb, _ = peak_kb("--root", str(root), "parts", "--json", script=PEAK)
    above_mb = (parts_kb - load_kb) / 1024
    print(f"M3 (generated tree, not big5): {len(three_levels.map_ids(7, 3))} maps")
    print(f"  exit codes {sorted({c for c, _t, _o in runs})}")
    print(f"  times {[round(t, 2) for _c, t, _o in runs]}, median {median:.2f} s")
    print(
        f"  peak RSS: parts --json {parts_kb / 1024:.1f} MB, load and facts read {load_kb / 1024:.1f} MB"
    )
    print(f"  peak RSS above the load and the facts read: {above_mb:.1f} MB")
    print(f"  output {out_bytes} bytes, plan file {plan_bytes} bytes")
    ok = all(c == 0 for c, _t, _o in runs) and median <= 10 and above_mb <= 50
    ok = ok and out_bytes <= 50 * 1024 * 1024
    print(f"M3: {'pass' if ok else 'fail'} on this tree")
    return ok


def _self_map() -> tuple[Model, Meaning, dict[str, float]]:
    cfg = config.load(ROOT)
    top = nest.load(cfg).top
    model, meaning = top.model, top.meaning
    inside = [c for c in model.components if c.kind != "actor"]
    steps = [s for j in meaning.journeys for s in j.steps]
    mean = statistics.mean
    stats = {
        "does": mean(len(c.does) for c in inside),
        "interface": mean(len(c.interface) for c in inside),
        "claims": mean(len(c.implemented_by) for c in inside),
        "flows_per_card": len(model.flows) / len(model.components),
        "refs": mean(len(f.source_refs) for f in model.flows),
        "relation": mean(len(meaning.relation(f)) for f in model.flows),
        "journeys_per_card": len(meaning.journeys) / len(model.components),
        "steps": mean(len(j.steps) for j in meaning.journeys),
        "say": mean(len(s.say) for s in steps),
        "covers": mean(len(j.covers) for j in meaning.journeys),
    }
    return model, meaning, stats


def _text(n: int, seed: str) -> str:
    words = (seed + " gives the values to the next component. ") * (n // 40 + 1)
    return words[:n]


def _generated(stats: dict[str, float]) -> tuple[Model, Meaning]:
    ids = [f"Card{i:02d}" for i in range(CARDS)]
    claims = round(stats["claims"])
    components = tuple(
        Component(
            id=cid,
            does=_text(round(stats["does"]), cid),
            interface=_text(round(stats["interface"]), cid),
            implemented_by=tuple(f"pkg.part.{cid.lower()}.m{k}" for k in range(claims)),
            entry="run",
            region="work",
            x=20 + 190 * (i % 8),
            y=60 + 92 * (i // 8),
            source_review="0" * 64,
        )
        for i, cid in enumerate(ids)
    )
    flow_count = round(stats["flows_per_card"] * CARDS)
    pairs = [(ids[i], ids[(i + d) % CARDS]) for d in range(1, CARDS) for i in range(CARDS)]
    seen = pairs[:flow_count]
    refs = round(stats["refs"])
    flows = tuple(
        Flow(
            a,
            b,
            f"artifact {k}",
            "data",
            source_refs=tuple(f"pkg.part.{a.lower()}.m{r}@{'0' * 64}" for r in range(refs)),
            review_digest="0" * 64,
        )
        for k, (a, b) in enumerate(seen)
    )
    journeys = tuple(
        Journey(
            id=f"sequence-{j}",
            label=f"Sequence {j}",
            covers=tuple(
                f'["function","pkg.part.card{j:02d}.m0","","run{c}"]'
                for c in range(round(stats["covers"]))
            ),
            steps=tuple(
                Step(
                    acts=(flows[(j + s) % len(flows)].dst,),
                    measures=(),
                    edge=flows[(j + s) % len(flows)].edge,
                    say=_text(round(stats["say"]), f"step {s}"),
                )
                for s in range(round(stats["steps"]))
            ),
        )
        for j in range(round(stats["journeys_per_card"] * CARDS))
    )
    model = Model(
        canvas=(1600, 600),
        containers=(Container(id="part", label="PART", box=(0, 0, 1600, 600), tone="server"),),
        regions=(Region(id="work", label="WORK", box=(10, 40, 1580, 550), container="part"),),
        components=components,
        flows=flows,
        flow_kinds=(),
    )
    meaning = Meaning(
        plain={cid: f"the {cid.lower()} part" for cid in ids},
        relations={f.edge: _text(round(stats["relation"]), f.artifact) for f in flows},
        journeys=journeys,
    )
    return model, meaning


def _values(path: Path) -> int:
    """Count the values that the model reader counts for the file."""
    counted = [0]
    original = model_load._File.count

    def count(self: Any, node: Any, depth: int) -> None:
        counted[0] += 1
        original(self, node, depth)

    model_load._File.count = count  # type: ignore[method-assign]
    try:
        model_load.read(path, path.name, path.parent)
    finally:
        model_load._File.count = original  # type: ignore[method-assign]
    return counted[0]


def m4(base: Path) -> bool:
    model, meaning, stats = _self_map()
    print(
        f"M4: self-map {len(model.components)} components, {len(model.flows)} flows, "
        f"{len(meaning.journeys)} sequences"
    )
    files = sorted((ROOT / "map").glob("*.py"))
    total = sum(f.stat().st_size for f in files if f.name != "contract.py")
    print(f"  self-map model files: {total} bytes, {_values(ROOT / 'map' / 'model.py')} values")
    print("  means of the self-map: " + ", ".join(f"{k} {v:.1f}" for k, v in stats.items()))
    gen_model, gen_meaning = _generated(stats)
    path = base / "m4" / "generated.py"
    path.parent.mkdir(parents=True)
    path.write_text(model_convert.source_text("A generated nested map.", gen_model, gen_meaning))
    size = path.stat().st_size
    values = _values(path)
    print(
        f"  generated: {len(gen_model.components)} components, {len(gen_model.flows)} flows, "
        f"{len(gen_meaning.journeys)} sequences"
    )
    print(f"  size {size} bytes ({size / 1024:.1f} KB), {values} values")
    ok = size <= MAX_BYTES and values <= MAX_VALUES
    print(f"M4: {'pass' if ok else 'fail'} (limits {MAX_BYTES} bytes, {MAX_VALUES} values)")
    return ok


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        results = [m3(base), m4(base)]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
