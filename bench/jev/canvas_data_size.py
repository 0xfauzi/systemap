"""C1 of the nested canvas design: the size of the canvas data of a tree with 50 maps.

Acceptance (written before the run, from docs/design/nested-canvas.md, step 1): the
canvas data of the M11 tree (50 maps, 40 cards in each map) is at most 2 MB (2,097,152
bytes) raw. The raw size is the UTF-8 bytes of `canvas_data.text`. Pass or fail.

These values are also given. They have no acceptance value:

- the bytes of the same text after gzip at level 6,
- the time of `canvas_data.build` and `canvas_data.text`, 3 runs, with the caches of
  the router, the evidence, and the claims empty before each run,
- the same three values for the map of this repository, from its stored facts.

The M11 tree is the fixture of `bench/jev/nested_tree_pages.py` on the branch
claude/nested-step-8 (commit c820839). That script is not on this branch, so `files`
below is a copy of its fixture writer with no change. The top map has 7 cards that open
a map and 33 other cards. Each map on level 1 has 3 cards that open a map, 36 other
cards, and 1 actor. Each map on level 2 has 1 card that opens a map, 38 other cards, and
1 actor. Each map on level 3 has 39 cards and 1 actor. The fixture is not big5, and no
real repository has this form.

The script writes the tree in a new temporary folder and runs `systemap place` and
`systemap extract` in this process. It does not run `refresh`, because the canvas data
needs only the positions and the facts. The data is built without the open lines of
the judgement (`open_lines=None`). The script sends no data out.

Run from the repository root: uv run python bench/jev/canvas_data_size.py
"""

from __future__ import annotations

import gzip
import statistics
import sys
import tempfile
import time
from pathlib import Path

from systemap import assurance, canvas_data, config, evidence, facts_file, nest, route
from systemap.cli import main

RAW_LIMIT = 2_097_152
RUNS = 3
CONFIG = 'name = "fifty maps"\n[package_roots]\n"pkg" = "pkg"\n'
HEAD = "from systemap import Component, Container, Flow, Meaning, Model, Region\n"
WORDS = ("keeps", "reads", "sends", "checks", "writes", "gives")


# ---- the fixture writer of nested_tree_pages.py (c820839), with no change ----------


def _plain(n: int) -> str:
    return f"{WORDS[n % len(WORDS)]} the records {n}"


def _card(cid: str, claim: str, entry: str, opens: str = "") -> str:
    where = f', map="{opens}"' if opens else ""
    return (
        f'    Component(id="{cid}", does="Does one task.", implemented_by=("{claim}",), '
        f'entry="{entry}", region="work"{where}),\n'
    )


def _actor(cid: str) -> str:
    return f'    Component(id="{cid}", does="An adjacent component.", kind="actor", container="around"),\n'


def _model(name: str, cards: list[str], ids: list[str]) -> str:
    flows = [(a, b) for a, b in zip(ids, ids[1:], strict=False)]
    return (
        HEAD
        + "CONTAINERS = (\n"
        + '    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),\n'
        + '    Container(id="part", label="PART", box=(0, 0, 0, 0), tone="server"),\n)\n'
        + 'REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="part"),)\n'
        + "COMPONENTS = (\n"
        + "".join(cards)
        + ")\nFLOWS = (\n"
        + "".join(f'    Flow("{a}", "{b}", "record", "data"),\n' for a, b in flows)
        + ")\n"
        + "MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, "
        + "components=COMPONENTS, flows=FLOWS, flow_kinds=())\n"
        + "MEANING = Meaning(plain={"
        + ", ".join(f'"{cid}": "{_plain(k)}"' for k, cid in enumerate(ids))
        + "}, relations={"
        + ", ".join(f'("{a}", "{b}"): "{a} sends the record to {b}."' for a, b in flows)
        + "})\n"
    )


def _file(map_id: str) -> str:
    return map_id.lower().replace("/", "_") + ".py"


def _leaves(
    package: str, prefix: str, count: int, out: dict[str, str]
) -> tuple[list[str], list[str]]:
    cards, ids = [], []
    for k in range(count):
        cid = f"{prefix}{k}"
        name = f"{prefix.lower()}{k}"
        out[f"{package.replace('.', '/')}/{name}.py"] = f"def run_{k}() -> int:\n    return {k}\n"
        cards.append(_card(cid, f"{package}.{name}", f"run_{k}"))
        ids.append(cid)
    return cards, ids


def _map(
    out: dict[str, str],
    map_id: str,
    package: str,
    opens: list[str],
    leaves: tuple[str, int],
    actor: str,
) -> None:
    """Write one model file with its cards that open a map, its other cards, and its actor."""
    out[f"{package.replace('.', '/')}/__init__.py"] = ""
    cards = [_actor(actor)] if actor else []
    ids = [actor] if actor else []
    for card in opens:
        child = f"{map_id}/{card}" if map_id else card
        cards.append(_card(card, f"{package}.{card.lower()}.*", "run_0", _file(child)))
        ids.append(card)
    more, more_ids = _leaves(package, leaves[0], leaves[1], out)
    out["map/model.py" if not map_id else f"map/{_file(map_id)}"] = _model(
        map_id or "top", cards + more, ids + more_ids
    )


def files() -> dict[str, str]:
    out = {"systemap.toml": CONFIG}
    _map(out, "", "pkg", [f"P{i}" for i in range(7)], ("T", 33), "")
    for i in range(7):
        p = f"P{i}"
        _map(out, p, f"pkg.p{i}", [f"Q{j}" for j in range(3)], ("A", 36), "T0")
        for j in range(3):
            q = f"{p}/Q{j}"
            _map(out, q, f"pkg.p{i}.q{j}", ["Deep"], ("B", 38), "A0")
            _map(out, f"{q}/Deep", f"pkg.p{i}.q{j}.deep", [], ("C", 39), "B0")
    return out


# ---- the measurement ---------------------------------------------------------------


def _write(root: Path) -> None:
    for rel, text in files().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _commands(root: Path) -> dict[str, tuple[int, float]]:
    """Run place and extract in this process. Give the exit code and the seconds."""
    codes = {}
    for command in ("place", "extract"):
        began = time.perf_counter()
        code = main(["--root", str(root), command])
        codes[command] = (code, time.perf_counter() - began)
    return codes


def _measure(root: Path) -> tuple[int, int, int, list[float]]:
    """Give the map count, the raw bytes, the gzip bytes, and the seconds of each run."""
    cfg = config.load(root)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    times, text = [], ""
    for _run in range(RUNS):
        route.clear_routed()
        evidence.clear_evidence()
        assurance.clear_claims()
        tree = nest.load(cfg)
        began = time.perf_counter()
        text = canvas_data.text(canvas_data.build(cfg, tree, facts))
        times.append(time.perf_counter() - began)
    raw = text.encode("utf-8")
    return len(tree.maps), len(raw), len(gzip.compress(raw, compresslevel=6)), times


def _row(name: str, found: tuple[int, int, int, list[float]], limit: int | None) -> bool:
    maps, raw, packed, times = found
    passed = limit is None or raw <= limit
    verdict = "" if limit is None else ("pass" if passed else "fail")
    shown = ", ".join(f"{t:.2f}" for t in times)
    print(
        f"| {name} | {maps} | {raw:,} | {packed:,} | {shown} | "
        f"{statistics.median(times):.2f} | {verdict} |"
    )
    return passed


def main_run() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root)
        codes = _commands(root)
        print("exit codes and seconds:", {k: (c, round(t, 1)) for k, (c, t) in codes.items()})
        if any(code != 0 for code, _t in codes.values()):
            print("failure: a command did not exit 0. No size is measured.")
            return 1
        fifty = _measure(root)
    own = _measure(Path.cwd())
    print("| Tree | Maps | Raw bytes | gzip -6 bytes | Times (s) | Median (s) | Result |")
    print("|---|---|---|---|---|---|---|")
    passed = _row("M11 tree", fifty, RAW_LIMIT)
    _row("this repository", own, None)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main_run())
