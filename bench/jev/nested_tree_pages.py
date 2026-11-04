"""M11 of the nested parts design: the size of the pages of a tree with 50 maps.

Acceptance (written before the run, from the design of the nested parts, section
"Measurements", M11). On a tree of 50 maps on 3 nested levels, with 40 cards or fewer in
each map:

- Each page is at most 1.5 MB (1,572,864 bytes).
- The Map tree panel and the search index of a page are at most 150 KB (153,600 bytes)
  together on each page. The value is the bytes of the panel HTML plus the bytes of the
  `tree` record in the page data, in the form that the page embeds.
- The parent context mark of each nested page is at most 8 KB (8,192 bytes), and the
  compact preview of each nested map is at most 8 KB.
- The full output of `systemap refresh` (the output directory) is at most 75 MB
  (78,643,200 bytes).

The tree: the top map has 7 cards that open a map and 33 other cards. Each map on level 1
has 3 cards that open a map, 36 other cards, and 1 actor. Each map on level 2 has 1 card
that opens a map, 38 other cards, and 1 actor. Each map on level 3 has 39 cards and 1
actor. Thus each map has 40 cards, and the tree has 1 + 7 + 21 + 21 = 50 maps and 1,902
source modules. Each card has its own module, a card text of 19 to 21 characters, and one
flow to the next card. (Run 1 used a card text of 50 characters. A card holds about 26
characters, so `refresh` stopped and wrote no page. Run 2 gave no card an entry, so
`refresh` stopped again and wrote no page. Now each card has an entry: the function of its
module, or `run_0` for a card that opens a map. The acceptance values did not change.) The fixture is not big5, and no real repository has this form.

The script writes the tree in a new temporary folder, runs `systemap place`, `extract`,
and `refresh` in this process, and measures the files. It sends no data out.

Run from the repository root: uv run python bench/jev/nested_tree_pages.py
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import time
from pathlib import Path

from systemap import config, nest, page, page_context
from systemap.cli import main

PAGE_LIMIT = 1_572_864
TREE_LIMIT = 153_600
SMALL_LIMIT = 8_192
OUTPUT_LIMIT = 78_643_200
CONFIG = 'name = "fifty maps"\n[package_roots]\n"pkg" = "pkg"\n'
HEAD = "from systemap import Component, Container, Flow, Meaning, Model, Region\n"
WORDS = ("keeps", "reads", "sends", "checks", "writes", "gives")


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


TREE_PANEL = re.compile(r'<details class="map-links map-tree".*?</details>', re.S)


def _tree_bytes(html: str) -> int:
    start = html.index("window.systemapWorkspace=") + len("window.systemapWorkspace=")
    raw = html[start : html.index(";</script>", start)]
    tree = json.loads(raw)["tree"]
    data = json.dumps(tree, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    panel = TREE_PANEL.search(html)
    return len(data.encode("utf-8")) + (len(panel.group(0).encode("utf-8")) if panel else 0)


def _write(root: Path) -> None:
    for rel, text in files().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _commands(root: Path) -> dict[str, tuple[int, float]]:
    """Run place, extract, and refresh in this process. Give the exit code and seconds."""
    codes = {}
    for command in ("place", "extract", "refresh"):
        extra = ["--quiet"] if command == "refresh" else []
        began = time.perf_counter()
        code = main(["--root", str(root), command, *extra])
        codes[command] = (code, time.perf_counter() - began)
    return codes


Row = tuple[str, int, int | None]


def _measure(cfg: config.Config, tree: nest.Tree, pages: list[Path]) -> list[Row]:
    sizes = [p.stat().st_size for p in pages]
    trees = [_tree_bytes(p.read_text(encoding="utf-8")) for p in pages]
    marks = [len(page_context.mark(tree, m).encode("utf-8")) for m in tree.maps if m.id]
    previews = [len(page.preview(m).encode("utf-8")) for m in tree.maps if m.id]
    output = sum(p.stat().st_size for p in cfg.out_path.rglob("*") if p.is_file())
    return [
        ("pages", len(pages), None),
        ("page bytes (max)", max(sizes), PAGE_LIMIT),
        ("page bytes (min)", min(sizes), None),
        ("tree and index bytes (max)", max(trees), TREE_LIMIT),
        ("tree and index bytes (min)", min(trees), None),
        ("parent context mark bytes (max)", max(marks), SMALL_LIMIT),
        ("compact preview bytes (max)", max(previews), SMALL_LIMIT),
        ("output bytes", output, OUTPUT_LIMIT),
    ]


def _report(rows: list[Row]) -> bool:
    """Print the table of the results. Tell if each value is in its acceptance limit."""
    print("| Value | Result | Acceptance | Pass |")
    print("|---|---|---|---|")
    for name, value, limit in rows:
        shown = "" if limit is None else f"at most {limit:,}"
        verdict = "" if limit is None else ("pass" if value <= limit else "fail")
        print(f"| {name} | {value:,} | {shown} | {verdict} |")
    return all(limit is None or value <= limit for _name, value, limit in rows)


def main_run() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root)
        codes = _commands(root)
        print("exit codes and seconds:", {k: (c, round(t, 1)) for k, (c, t) in codes.items()})
        cfg = config.load(root)
        tree = nest.load(cfg)
        levels = max(len(m.id.split("/")) for m in tree.maps if m.id)
        print(f"maps: {len(tree.maps)}, levels below the top: {levels}")
        print(f"largest map: {max(len(m.model.components) for m in tree.maps)} cards")
        pages = sorted(cfg.out_path.rglob("index.html"))
        if len(pages) != len(tree.maps):
            print(f"failure: {len(pages)} pages for {len(tree.maps)} maps. No size is measured.")
            return 1
        passed = _report(_measure(cfg, tree, pages))
        return 0 if passed and all(code == 0 for code, _t in codes.values()) else 1


if __name__ == "__main__":
    sys.exit(main_run())
