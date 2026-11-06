"""C2 and C3 of the nested canvas design: frame time and load time of the canvas page.

Acceptance values, written before the first run on 2026-11-05, from
docs/design/nested-canvas.md (step 2 and the section "Performance"):

- C2: the p95 frame interval of each scenario below, with 4 times CPU throttling
  (`Emulation.setCPUThrottlingRate`), is at most 33 ms. The browser starts a frame at
  a 60 Hz tick. Thus an interval is a multiple of 16.67 ms, and 33.33 ms (two ticks, 30
  frames each second) is the value that "33 ms" names. The timer of the ticks has a
  small error. The limit is 33.33 ms plus 5 percent: 35.0 ms. Pass or fail for each
  scenario.
- C2 at normal CPU speed (1 times): the p95 frame interval is at most 16.7 ms plus 5
  percent: 17.5 ms. This is the same limit as the prototype measurement. Pass or fail
  for each scenario.
- C3: the time from the start of the navigation to an interactive map
  (`systemapCanvas.ready`: the first frame is drawn and the input handlers are
  attached), for the tree of 50 maps, at normal CPU speed, is at most 1,500 ms. The
  same time with 4 times CPU throttling is also given. It has no acceptance value.

The scenarios. Each one draws 180 frames. The camera changes at each frame, as a move
does. Thus each frame is drawn at half resolution (the rule for a moving camera).

- `pan-fit`: the top map at fit, with a pan of 200 screen pixels to the left and right.
- `all-open`: the camera on the box of the cards of the top map that open a map. The
  zoom goes from 0.6 to 1.4 times the fit of that box. Each such card shows the preview
  of its map, and the cards near the middle start to open.
- `dive`: from the top map at fit to the deepest map below the first card that opens a
  map, and back out. The scale moves in log space.

The driver also has two modes for a stop (added on 2026-11-06, for the A/B of the fades
after a stop). `main` does not run them, and they have no acceptance value here:

- `dive-stop`: a move from the top fit to the part 0.2 of the dive, and then no camera
  change for 700 ms.
- `pan-stop`: the pan of `pan-fit` at the camera of that part of the dive, and then no
  camera change for 700 ms.

For the 700 ms after the move, the driver gives the count of animation frames, the largest
interval, and the count of intervals of more than 35 ms.

The data:

- `M11 tree`: the canvas data (`canvas_data.build`) of the M11 tree (50 maps, 40 cards
  in each map), from the fixture writer of `canvas_data_size.py`, after `place` and
  `extract`. Scenarios pan-fit, all-open and dive.
- `M11 shape`: a generated tree with the same form (`nested_tree`). The performance
  test in CI (tests/test_canvas_frames.py) uses it, because the real build takes about
  30 s. Scenarios pan-fit, all-open and dive.
- `400 cards` and `1,500 cards`: one generated map (`grid_map`) with that many cards in
  a grid, and one flow from each card to the next card. Scenarios pan-fit and dive, and
  pan-fit only for 1,500 cards, as in the prototype measurement.

The page is the real canvas page (`canvas_page.build`) with the theme of this
repository. The browser is the Chromium of Playwright, headless, with a viewport of
1440 x 900 and a device pixel ratio of 1. The host has no GPU. Thus Chromium paints in
software, and a device with a GPU can be faster. That difference is not measured.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/canvas_frames.py
"""

from __future__ import annotations

import contextlib
import functools
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "canvas_frames.js"
FRAMES = 180
LIMITS = {1: 17.5, 4: 35.0}
LOAD_LIMIT = 1500.0
TREE_SCENARIOS = ("pan-fit", "all-open", "dive")
CARD = (150, 56)
PITCH = (190, 100)
WORDS = ("keeps", "reads", "sends", "checks", "writes", "gives")


# ---- generated data in the format of canvas_data ---------------------------------


def _card(cid: str, n: int, x: float, y: float, opens: str = "") -> dict[str, Any]:
    card: dict[str, Any] = {
        "as": ["unknown", "missing"],
        "b": [x, y, CARD[0], CARD[1]],
        "d": "Does one task and gives the result to the next part.",
        "id": cid,
        "k": "component",
        "m": [f"pkg.{cid.lower()}"],
        "p": f"{WORDS[n % len(WORDS)]} the records {n}",
        "r": "work",
        "s": "built",
    }
    if opens:
        card["o"] = opens
    return card


def _route(a: list[float], b: list[float]) -> tuple[list[list[float]], list[float]]:
    """Give right-angle route points from card box `a` to card box `b`, and a label box."""
    if abs(a[1] - b[1]) < 1:
        y = a[1] + CARD[1] / 2
        p = [[a[0] + CARD[0], y], [b[0], y]]
        return p, [a[0] + CARD[0] + 4, y - 15, 36.5, 13]
    x0, x1, gy = a[0] + CARD[0] / 2, b[0] + CARD[0] / 2, a[1] + CARD[1] + 20
    return [[x0, a[1] + CARD[1]], [x0, gy], [x1, gy], [x1, b[1]]], [x0 + 4, gy - 15, 36.5, 13]


def _map(
    map_id: str, ids: list[str], cols: int, opens: dict[str, str], actor: str = ""
) -> dict[str, Any]:
    left = 230 if actor else 40
    cards = [
        _card(
            cid,
            n,
            left + 40 + (n % cols) * PITCH[0],
            108 + (n // cols) * PITCH[1],
            opens.get(cid, ""),
        )
        for n, cid in enumerate(ids)
    ]
    rows = (len(ids) + cols - 1) // cols
    width, height = left + 80 + cols * PITCH[0], 160 + rows * PITCH[1]
    flows = []
    for a, b in zip(cards, cards[1:], strict=False):
        points, label = _route(a["b"], b["b"])
        flows.append(
            {
                "a": "record",
                "as": ["unknown", "missing"],
                "ev": "structural",
                "k": "data",
                "l": "data",
                "lb": label,
                "p": points,
                "s": a["id"],
                "t": b["id"],
            }
        )
    boxes = [
        {"b": [left, 16, width - left - 16, height - 32], "id": "part", "n": "PART", "t": "server"}
    ]
    out: dict[str, Any] = {
        "id": map_id,
        "size": [width, height],
        "layers": [],
        "flows": flows,
        "regions": [
            {
                "b": [left + 20, 68, width - left - 56, height - 104],
                "c": "part",
                "id": "work",
                "n": "WORK",
            }
        ],
    }
    if actor:
        boxes.insert(
            0, {"b": [16, 16, 190, height - 32], "id": "around", "n": "AROUND", "t": "host"}
        )
        act = _card(actor, 0, 36, height / 2 - CARD[1] / 2)
        act.update(k="actor", s="", m=[])
        cards.insert(0, act)
        points = [[36 + CARD[0], height / 2], [cards[1]["b"][0], height / 2]]
        flows.insert(
            0,
            {
                "a": "record",
                "as": ["unknown", "missing"],
                "ev": "external",
                "k": "data",
                "l": "data",
                "lb": [190, height / 2 - 15, 36.5, 13],
                "p": points,
                "s": actor,
                "t": cards[1]["id"],
            },
        )
    out.update(boxes=boxes, cards=cards)
    return out


def grid_map(n: int) -> dict[str, Any]:
    """Give the canvas data of one map with `n` cards in a grid."""
    cols = max(1, round((n * 1.6) ** 0.5))
    m = _map("", [f"C{k}" for k in range(n)], cols, {})
    return {"v": 1, "name": f"{n} cards", "rev": "", "unknown": [], "judged": False, "maps": [m]}


def nested_tree() -> dict[str, Any]:
    """Give generated canvas data with the form of the M11 tree: 50 maps of 40 cards.

    The top map has 7 cards that open a map. A map on level 1 has 3 such cards and an
    actor, a map on level 2 has 1 and an actor, and a map on level 3 has none and an
    actor. A nested map has a port for its actor and for the next card in its parent."""
    maps: list[dict[str, Any]] = []
    _add(maps, "", "P", 7, "", 0, "")
    data = {"v": 1, "name": "M11 shape", "rev": "", "unknown": [], "judged": False, "maps": maps}
    return data


def _ports(actor: str, first: str, nxt: str, height: float) -> list[dict[str, Any]]:
    """Give the port of the actor of a nested map, and the port of the next card in its parent.

    The actor card is at the left of the map. Its line to the frame goes to the left."""
    middle = height / 2
    ports: list[dict[str, Any]] = [
        {
            "at": [186, middle],
            "d": "in",
            "f": 0,
            "fp": [[36, middle], [0, middle]],
            "i": first,
            "pf": [],
            "sd": "right",
            "x": actor,
        }
    ]
    if nxt:
        ports.append({"d": "out", "pf": [0], "x": nxt})
    return ports


def _add(
    maps: list[dict[str, Any]],
    map_id: str,
    prefix: str,
    opens: int,
    actor: str,
    depth: int,
    nxt: str,
) -> None:
    """Add a map of 40 cards and, below its first `opens` cards, their maps."""
    ids = [f"{prefix}{k}" for k in range(40 - (1 if actor else 0))]
    children = {ids[k]: f"{map_id}/{ids[k]}" if map_id else ids[k] for k in range(opens)}
    m = _map(map_id, ids, 14, children, actor)
    if map_id:
        m["ports"] = _ports(actor, ids[0], nxt, m["size"][1])
    maps.append(m)
    letter = "ABC"[depth] if depth < 3 else "D"
    for k in range(opens):
        _add(
            maps,
            children[ids[k]],
            letter,
            (3, 1, 0)[depth],
            f"{prefix}{opens}",
            depth + 1,
            ids[k + 1],
        )


def m11_tree() -> dict[str, Any]:
    """Give the real canvas data of the M11 tree. It takes about 30 s."""
    import canvas_data_size as c1  # noqa: PLC0415  (a neighbour script in bench/jev)

    from systemap import canvas_data, config, facts_file, nest  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        c1._write(root)
        with contextlib.redirect_stdout(io.StringIO()):
            codes = c1._commands(root)
        if any(code != 0 for code, _t in codes.values()):
            raise SystemExit(f"failure: place or extract did not exit 0: {codes}")
        cfg = config.load(root)
        facts = facts_file.read_facts(cfg.facts_path, cfg.root)
        return canvas_data.build(cfg, nest.load(cfg), facts)


# ---- the browser measurements -------------------------------------------------------


def write_page(data: dict[str, Any], out: Path) -> Path:
    """Write the real canvas page of `data` with the theme of this repository."""
    from systemap import canvas_page, config, nest  # noqa: PLC0415

    root = HERE.parent.parent
    out.write_text(
        canvas_page.build(nest.load(config.load(root)).top.theme, data), encoding="utf-8"
    )
    return out


@functools.cache
def node() -> str | None:
    """Give the Node command if Node and the Playwright package with Chromium are there."""
    found = shutil.which("node")
    if found is None:
        return None
    probe = subprocess.run(
        [found, str(DRIVER), "--probe"], capture_output=True, text=True, timeout=120, check=False
    )
    return found if probe.returncode == 0 else None


def run(page: Path, mode: str, rate: int, frames: int = FRAMES) -> dict[str, Any]:
    """Run one scenario (or `load`) in a new browser. Give the result object of the driver."""
    found = node()
    if found is None:
        raise RuntimeError("Node with the Playwright package and Chromium is necessary.")
    proc = subprocess.run(
        [found, str(DRIVER), str(page), mode, str(rate), str(frames)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return dict(json.loads(proc.stdout))


def _row(name: str, mode: str, rate: int, found: dict[str, Any]) -> bool:
    if mode == "load":
        passed = rate != 1 or found["ready"] <= LOAD_LIMIT
        verdict = ("pass" if passed else "fail") if rate == 1 else "information"
        print(f"| {name} | C3 load | {rate}x | {found['ready']:.0f} ms | | | {verdict} |")
        return passed
    passed = found["p95"] <= LIMITS[rate]
    print(
        f"| {name} | {mode} | {rate}x | {found['median']:.1f} | {found['p95']:.1f} | "
        f"{found['max']:.1f} | {'pass' if passed else 'fail'} |"
    )
    return passed


def cases(tree_name: str) -> list[tuple[str, str]]:
    return [
        *((tree_name, s) for s in TREE_SCENARIOS),
        ("400 cards", "pan-fit"),
        ("400 cards", "dive"),
        ("1,500 cards", "pan-fit"),
    ]


def main() -> int:
    if node() is None:
        print("failure: Node with the Playwright package and Chromium is necessary.")
        return 1
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        pages = {
            "M11 tree": write_page(m11_tree(), out / "m11.html"),
            "M11 shape": write_page(nested_tree(), out / "shape.html"),
            "400 cards": write_page(grid_map(400), out / "g400.html"),
            "1,500 cards": write_page(grid_map(1500), out / "g1500.html"),
        }
        print("| Data | Scenario | CPU | Median (ms) | p95 (ms) | Max (ms) | Result |")
        print("|---|---|---|---|---|---|---|")
        for rate in (4, 1):
            for tree in ("M11 tree", "M11 shape"):
                ok &= _row(tree, "load", rate, run(pages[tree], "load", rate))
            for name, mode in cases("M11 tree") + [("M11 shape", s) for s in TREE_SCENARIOS]:
                ok &= _row(name, mode, rate, run(pages[name], mode, rate))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    sys.exit(main())
