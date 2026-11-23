"""R2: a canvas page of the map of this repository at the region level.

R1 (`region_level.py`) gave the counts of the region level. This script makes a page of
that level with the real router and the real canvas renderer, so that a person can see it
and a program can measure its labels. It is a prototype. It changes no file of the
repository.

The script makes a small project in a temporary folder. Its model has one card for each
region of the map of this repository and one card for each actor. For the selected layer,
each directed line of R1 is one flow. Its artifact is the artifact of the flow when the
line stands for one flow, and "N flows" when it stands for more. Its kind is the kind that
most of its flows have, `data` or `control`. A flow in one region gives no line. Then the
script runs `systemap place`, `extract` and `render` in that folder and copies the page.

Acceptance values, written before the first run on 2026-11-15, for the layer All (28
directed lines in R1), with `canvas_labels.js` at the fit:

1. At 1440 x 900 pixels, each line that has a label box has a drawn label with an alpha of
   0.99 or more and a font size of 9 px or more.
2. At 1440 x 900 pixels, no label plate goes into a card, and no two label plates go into
   each other.
3. The values at 1366 x 768 and 1280 x 720 pixels are given. They have no acceptance value.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/region_level_page.py OUT.html [LAYER]
LAYER is a layer ID of the map, or "all" (the default).
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import canvas_labels  # noqa: E402

HEAD = "from systemap import Component, Container, Flow, Meaning, Model, Region\n"
CONFIG = 'name = "systemap: region level"\n[package_roots]\n"pkg" = "pkg"\n'


def _name(label: str) -> str:
    return "".join(word.capitalize() for word in label.split())


def _lines(layer: str) -> tuple[list[tuple[str, int]], list[str], dict[tuple[str, str], Any]]:
    """Give the region cards (name, count of components), the actors, and the flows of
    each directed line of the layer."""
    from systemap import config, nest  # noqa: PLC0415
    from systemap.model import reading  # noqa: PLC0415

    top = nest.load(config.load(ROOT)).top
    model = top.model
    names = {r.id: _name(r.label) for r in model.regions}
    end = {}
    count: Counter[str] = Counter()
    actors = []
    for c in model.components:
        if c.kind == "actor":
            actors.append(c.id)
            end[c.id] = c.id
        else:
            end[c.id] = names[c.region or ""]
            count[names[c.region or ""]] += 1
    chosen = range(len(model.flows)) if layer == "all" else reading(model, top.meaning, layer)[0]
    lines: dict[tuple[str, str], Any] = {}
    for i in chosen:
        f = model.flows[i]
        a, b = end[f.src], end[f.dst]
        if a != b:
            lines.setdefault((a, b), []).append(f)
    regions = [(names[r.id], count[names[r.id]]) for r in model.regions]
    return regions, actors, lines


def _model(layer: str) -> dict[str, str]:
    regions, actors, lines = _lines(layer)
    out = {"systemap.toml": CONFIG, "pkg/__init__.py": ""}
    cards = []
    plain = {}
    for name, n in regions:
        out[f"pkg/{name.lower()}.py"] = "def run() -> int:\n    return 0\n"
        cards.append(
            f'    Component(id="{name}", does="This region has {n} components.", '
            f'implemented_by=("pkg.{name.lower()}",), entry="run", region="work"),\n'
        )
        plain[name] = f"{n} components"
    for actor in actors:
        cards.append(
            f'    Component(id="{actor}", does="An actor.", kind="actor", container="around"),\n'
        )
        plain[actor] = "an actor"
    flows = []
    relations = []
    for (a, b), found in lines.items():
        kinds = Counter(f.kind if f.kind in ("data", "control") else "data" for f in found)
        artifact = found[0].artifact if len(found) == 1 else f"{len(found)} flows"
        flows.append(f'    Flow("{a}", "{b}", "{artifact}", "{kinds.most_common(1)[0][0]}"),\n')
        relations.append(f'("{a}", "{b}"): "{a} has {len(found)} flows to {b}."')
    out["map/model.py"] = (
        HEAD
        + "CONTAINERS = (\n"
        + '    Container(id="around", label="OUTSIDE THE PACKAGE", box=(0, 0, 0, 0), tone="host"),\n'
        + '    Container(id="part", label="SYSTEMAP", box=(0, 0, 0, 0), tone="server"),\n)\n'
        + 'REGIONS = (Region(id="work", label="REGIONS", box=(0, 0, 0, 0), container="part"),)\n'
        + "COMPONENTS = (\n"
        + "".join(cards)
        + ")\nFLOWS = (\n"
        + "".join(flows)
        + ")\nMODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, "
        + "components=COMPONENTS, flows=FLOWS, flow_kinds=())\n"
        + "MEANING = Meaning(plain={"
        + ", ".join(f'"{k}": "{v}"' for k, v in plain.items())
        + "}, relations={"
        + ", ".join(relations)
        + "})\n"
    )
    return out


def build(out: Path, layer: str) -> None:
    """Write the page of the region level for the layer at `out`."""
    from systemap.cli import main as cli  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in _model(layer).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as said:
            codes = [cli(["--root", str(root), c]) for c in ("place", "extract", "render")]
        if any(codes):
            raise SystemExit(f"place, extract or render did not exit 0: {codes}\n{said.getvalue()}")
        shutil.copyfile(root / "docs" / "map" / "index.html", out)


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    out = Path(sys.argv[1]).resolve()
    layer = sys.argv[2] if len(sys.argv) > 2 else "all"
    build(out, layer)
    print(f"page: {out}")
    rows = [r for r in canvas_labels._measure(out) if r["layer"] == "all" and r["at"] == "fit"]
    print("screen     zoom  lines full  min px  in card  in plate  drawn  alpha   px")
    passed = True
    for r in rows:
        print(
            f"{r['screen']:10} {r['zoom']:.3f} {r['boxed']:5} {r['full']:4} "
            f"{r['min_size'] or 0:7.1f} {r['in_card']:8} {r['in_plate']:9} "
            f"{r['drawn']:6} {r['alpha']:6.2f} {r['size']:4.1f}"
        )
        if r["screen"] == "1440x900":
            passed = (
                r["full"] == r["boxed"]
                and (r["min_size"] or 0) >= canvas_labels.SIZE
                and r["in_card"] == 0
                and r["in_plate"] == 0
            )
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
