"""Nested maps: a card that opens a map of its own.

A package with two subpackages is mapped as one top map of five cards,
two of which open a map: the Gateway card opens map/gateway.py and the
Style card opens map/style.py. Every command walks the tree: the check
runs on every map and holds each sub-map to exactly the modules its card
claims, coverage counts the modules once, a page is written per map with
the links up and down, a figure draws one map by id, place writes into
a sub-map's file, the judgement and describe lines carry the map's id,
and delta names the card and the map a moved module belongs to.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_keyboard import DRIVER, needs_node

from systemap import nest, place
from systemap.cli import main

TREE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": """
        from pkg.gateway.app import create_app


        def read(source: str) -> str:
            create_app()
            return source
    """,
    "pkg/writer.py": """
        from pkg.style.compiler import compile_guide


        def write(text: str) -> str:
            return compile_guide(text)
    """,
    "pkg/gateway/__init__.py": "",
    "pkg/gateway/app.py": """
        from pkg.gateway.routes import route
        from pkg.gateway.store import Store


        def create_app() -> Store:
            route("/")
            return Store()
    """,
    "pkg/gateway/routes.py": """
        from pkg.style.cache import Cache


        def route(path: str) -> Cache:
            return Cache()
    """,
    "pkg/gateway/store.py": """
        class Store:
            def record(self, key: str) -> None:
                pass
    """,
    "pkg/style/__init__.py": "",
    "pkg/style/cache.py": """
        class Cache:
            def get(self, key: str) -> str:
                return key
    """,
    "pkg/style/compiler.py": """
        from pkg.style.cache import Cache


        def compile_guide(text: str) -> str:
            return Cache().get(text)
    """,
}

CONFIG = """
name = "demo"
[package_roots]
"pkg" = "pkg"
"""

TOP = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (
    Container(id="outside", label="OUTSIDE", box=(0, 0, 0, 0), tone="host"),
    Container(id="system", label="SYSTEM", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (
    Region(id="edge", label="EDGE", box=(0, 0, 0, 0), container="system"),
    Region(id="core", label="CORE", box=(0, 0, 0, 0), container="system"),
)
COMPONENTS = (
    Component(id="User", does="Types the input.", kind="actor", container="outside"),
    Component(id="Reader", does="Reads the input.", implemented_by=("pkg.reader",), entry="read", region="edge"),
    Component(id="Gateway", does="The front door.", implemented_by=("pkg.gateway.*",), entry="create_app", region="edge", map="gateway.py"),
    Component(id="Style", does="Keeps and compiles the guides.", implemented_by=("pkg.style.*",), entry="compile_guide", region="core", map="style.py"),
    Component(id="Writer", does="Writes the output.", implemented_by=("pkg.writer",), entry="write", region="core"),
)
FLOWS = (
    Flow("User", "Reader", "input", "data"),
    Flow("Reader", "Gateway", "request", "control"),
    Flow("Gateway", "Style", "guide lookup", "data"),
    Flow("Style", "Writer", "guide", "data"),
)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"User": "the person", "Reader": "what reads", "Gateway": "the front door", "Style": "the guides", "Writer": "what writes"},
    relations={
        ("User", "Reader"): "The user types one input at a time.",
        ("Reader", "Gateway"): "The reader builds the app and hands it the request.",
        ("Gateway", "Style"): "The gateway looks a guide up by key.",
        ("Style", "Writer"): "The compiled guide is what the writer writes.",
    },
)
"""

GATEWAY = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="gateway", label="GATEWAY", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="serve", label="SERVE", box=(0, 0, 0, 0), container="gateway"),)
COMPONENTS = (
    Component(id="Reader", does="The card that calls in.", kind="actor", container="around"),
    Component(id="Style", does="The card the routes reach.", kind="actor", container="around"),
    Component(id="App", does="Builds the app.", implemented_by=("pkg.gateway.app",), entry="create_app", region="serve"),
    Component(id="Routes", does="Dispatches a path.", implemented_by=("pkg.gateway.routes",), entry="route", region="serve"),
    Component(id="Store", does="Keeps the records.", implemented_by=("pkg.gateway.store",), entry="Store", kind="store", region="serve"),
)
FLOWS = (
    Flow("Reader", "App", "request", "control"),
    Flow("App", "Routes", "dispatch", "control"),
    Flow("App", "Store", "record", "data"),
    Flow("Routes", "Style", "guide lookup", "data"),
)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"Reader": "what calls in", "Style": "the guides", "App": "the app", "Routes": "the routes", "Store": "the records"},
    relations={
        ("Reader", "App"): "The reader builds the app for each request.",
        ("App", "Routes"): "The app dispatches the path to a route.",
        ("App", "Store"): "The app records each request.",
        ("Routes", "Style"): "A route looks a guide up in the cache.",
    },
)
"""

STYLE = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="style", label="STYLE", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="keep", label="KEEP", box=(0, 0, 0, 0), container="style"),)
COMPONENTS = (
    Component(id="Gateway", does="The card that looks guides up.", kind="actor", container="around"),
    Component(id="Writer", does="The card that writes the guide.", kind="actor", container="around"),
    Component(id="Cache", does="Keeps the guides by key.", implemented_by=("pkg.style.cache",), entry="Cache", kind="store", region="keep"),
    Component(id="Compiler", does="Compiles a guide.", implemented_by=("pkg.style.compiler",), entry="compile_guide", region="keep"),
)
FLOWS = (
    Flow("Gateway", "Cache", "lookup", "data"),
    Flow("Cache", "Compiler", "compile on miss", "control"),
    Flow("Compiler", "Writer", "guide", "data"),
)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"Gateway": "the front door", "Writer": "what writes", "Cache": "the shelf", "Compiler": "what compiles"},
    relations={
        ("Gateway", "Cache"): "The gateway asks the cache by key.",
        ("Cache", "Compiler"): "On a miss the cache runs the compiler.",
        ("Compiler", "Writer"): "The compiled guide goes to the writer.",
    },
)
"""

MODELS = {"map/model.py": TOP, "map/gateway.py": GATEWAY, "map/style.py": STYLE}


def run(*argv: str) -> int:
    return main(list(argv))


@pytest.fixture
def nested(tmp_path: Path) -> Path:
    """The package, the three models placed by `systemap place`, the facts extracted."""
    write_tree(tmp_path, {**TREE, "systemap.toml": CONFIG, **MODELS})
    assert run("--root", str(tmp_path), "place") == 0
    assert run("--root", str(tmp_path), "extract") == 0
    return tmp_path


def edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text()
    assert old in text, old
    path.write_text(text.replace(old, new))


def add_child_route(root: Path) -> None:
    """Give the Gateway map one route owned by its Routes card."""
    edit(
        root,
        "pkg/gateway/routes.py",
        "def route(path: str) -> Cache:",
        'from fastapi import FastAPI\napp = FastAPI()\n\n@app.get("/read")\ndef route(path: str) -> Cache:',
    )
    assert run("--root", str(root), "extract") == 0


def test_parent_explicit_coverage_satisfies_child_judgement(nested: Path) -> None:
    from systemap import extract, judgement
    from systemap.config import load

    add_child_route(nested)
    facts = extract.read_facts(load(nested).facts_path)
    assert facts is not None
    point = next(p for p in facts["entry_points"] if p["module"] == "pkg.gateway.routes")
    identity = extract.entry_identity(point)
    top_path = nested / "map/model.py"
    source = top_path.read_text()
    source = source.replace(
        "from systemap import Component, Container, Flow, Meaning, Model, Region",
        "from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step",
    ).replace(
        "MEANING = Meaning(\n",
        'MEANING = Meaning(\n    journeys=(Journey("route", "Read route", '
        '(Step(("Reader",), (), ("Reader", "Gateway"), "Read."),), '
        f'starts="GET /read", covers=({identity!r},)),),\n',
    )
    top_path.write_text(source)
    lines = judgement.run_tree(nest.load(load(nested)), facts)
    assert not any("GET /read" in line and "has no journey" in line for line in lines)


def test_journeys_command_writes_child_route_in_child_model(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from systemap.config import load
    from systemap.jev_cli import cmd_journeys

    add_child_route(nested)
    child_path = nested / "map/gateway.py"
    source = child_path.read_text()
    source = source.replace(
        "from systemap import Component, Container, Flow, Meaning, Model, Region",
        "from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step",
    ).replace(
        "MEANING = Meaning(\n", "JOURNEYS = (\n)\nMEANING = Meaning(\n    journeys=JOURNEYS,\n"
    )
    child_path.write_text(source)
    cfg = load(nested)
    args = __import__("argparse").Namespace(root_path=cfg.root, limit=3, dry_run=True)
    assert cmd_journeys(args) == 0
    preview = capsys.readouterr().out
    assert "Gateway: GET /read (route) (map/gateway.py)" in preview

    toml = nested / "systemap.toml"
    toml.write_text(toml.read_text() + '\n[agent]\ncommand = "agent -p"\n')
    answer = json.dumps(
        {
            "id": "read-route",
            "label": "Read a route",
            "steps": [
                {
                    "edge": ["App", "Routes"],
                    "acts": ["App"],
                    "measures": [],
                    "say": "The app dispatches the route.",
                }
            ],
        }
    )

    def answer_command(command: str, question: str, cwd: Path, timeout: float) -> str:
        return answer

    args.dry_run = False
    assert cmd_journeys(args, run_command=answer_command) == 0
    output = capsys.readouterr().out
    assert "written into map/gateway.py" in output
    assert "read-route" in child_path.read_text()
    assert "read-route" not in (nested / "map/model.py").read_text()


def test_the_check_runs_on_every_map_and_counts_coverage_once(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tree = nest.load(__import__("systemap.config").config.load(nested))
    assert tree.ids == ["", "Gateway", "Style"]
    assert tree.get("Gateway").card == "Gateway" and tree.get("Gateway").rel == "map/gateway.py"
    assert tree.get("Gateway").inside == 3 and tree.get("Style").inside == 2
    # Nothing rendered yet: every rule but stale is clean, on every map.
    assert run("--root", str(nested), "check") == 1
    out = capsys.readouterr().out
    assert out.count("coverage:") == 1
    assert "coverage: 10 of 10 modules mapped, 1 an empty package marker" in out
    assert "claimed twice" not in out
    assert "map layout: has no errors (5 components, 4 orthogonal labeled edges" in out
    assert "Gateway: map layout: has no errors (5 components, 4 orthogonal labeled edges" in out
    assert "Style: map layout: has no errors (4 components, 3 orthogonal labeled edges" in out
    assert "Gateway: map routes: 0 edges across components other than its endpoints" in out
    assert "nesting" not in out
    for rel in ("index.html", "Gateway/index.html", "Style/index.html"):
        assert f"docs/map/{rel} has no rendered output." in out, rel
    assert out.rstrip().endswith("run: systemap refresh")
    assert run("--root", str(nested), "refresh") == 0
    assert (
        "map: The command updated docs/map/map.json, docs/map/index.html, docs/map/Gateway/index.html, docs/map/Style/index.html"
        in capsys.readouterr().out
    )
    assert run("--root", str(nested), "check") == 0
    assert run("--root", str(nested), "refresh") == 0
    assert (
        "The page agrees with the rendered model fields and the facts." in capsys.readouterr().out
    )


def test_the_exact_claim_rule_refuses_an_extra_and_a_missing_module(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--root", str(nested), "refresh") == 0
    # An extra module: a card of the Gateway map claims a module of Style.
    edit(
        nested,
        "map/gateway.py",
        'implemented_by=("pkg.gateway.routes",)',
        'implemented_by=("pkg.gateway.routes", "pkg.style.cache")',
    )
    assert run("--root", str(nested), "check") == 1
    out = capsys.readouterr().out
    assert "Gateway: nesting: 1 problem" in out
    assert (
        "Gateway:   the map inside Gateway (map/gateway.py) has a claim for pkg.style.cache, "
        "but Gateway has no claim for it (Routes)." in out
    )
    assert (
        "Gateway:   fix: In map/gateway.py, give each module of the parent component one claim. "
        "Use other parent components as actors." in out
    )
    # The top map's coverage is untouched: the parent claims the module once.
    assert "coverage: 10 of 10 modules mapped" in out and "claimed twice" not in out
    assert out.rstrip().endswith("Correct map/gateway.py. Then use systemap check.")
    # A missing module: the Store card drops its claim.
    edit(
        nested,
        "map/gateway.py",
        'implemented_by=("pkg.gateway.routes", "pkg.style.cache")',
        'implemented_by=("pkg.gateway.routes",)',
    )
    edit(
        nested,
        "map/gateway.py",
        'implemented_by=("pkg.gateway.store",), entry="Store"',
        'implemented_by=("pkg.gateway.routes:route",), entry="route"',
    )
    assert run("--root", str(nested), "check") == 1
    out = capsys.readouterr().out
    assert (
        "Gateway:   the map inside Gateway (map/gateway.py) has no claim for pkg.gateway.store, "
        "but Gateway has a claim for it." in out
    )
    # A symbol claim counts for no module, so it is neither extra nor twice.
    assert "claims pkg.gateway.routes" not in out
    assert "twice" not in out
    # Twice: two cards of the sub-map claim one module.
    edit(
        nested,
        "map/gateway.py",
        'implemented_by=("pkg.gateway.routes:route",), entry="route"',
        'implemented_by=("pkg.gateway.store", "pkg.gateway.app"), entry="Store"',
    )
    assert run("--root", str(nested), "check") == 1
    out = capsys.readouterr().out
    assert (
        "the map inside Gateway (map/gateway.py) has a claim for pkg.gateway.app 2 times (App, Store)"
        in out
    )
    assert run("--root", str(nested), "refresh") == 1
    assert (
        "map: The check found an error. Correct map/gateway.py. Then use systemap refresh."
        in capsys.readouterr().out
    )


def test_a_sub_maps_actors_are_cards_of_the_parent(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The Style map is written again without positions, so place lays its
    # boxes out whole for the extra actor.
    (nested / "map/style.py").write_text(STYLE.lstrip("\n"))
    edit(
        nested,
        "map/style.py",
        'Component(id="Writer", does="The card that writes the guide.", kind="actor", container="around"',
        'Component(id="Nobody", does="Not a card above.", kind="actor", container="around"),\n'
        '    Component(id="Style", does="Itself.", kind="actor", container="around"',
    )
    edit(nested, "map/style.py", '("Compiler", "Writer")', '("Compiler", "Nobody")')
    edit(nested, "map/style.py", 'Flow("Compiler", "Writer"', 'Flow("Compiler", "Nobody"')
    edit(nested, "map/style.py", '"Writer": "what writes"', '"Nobody": "nobody", "Style": "itself"')
    assert run("--root", str(nested), "place") == 0
    assert run("--root", str(nested), "check") == 1
    out = capsys.readouterr().out
    assert "Style: nesting: 2 problems" in out
    assert (
        "Style:   the map inside Style (map/style.py) has actor Nobody, which is not a "
        "component of the parent map. Nested-map actors are other parent components." in out
    )
    assert (
        "Style:   the map inside Style (map/style.py) has actor Style, the component that contains the map."
        in out
    )
    # An actor cannot open a map; a map that opens itself, or a missing file, is refused.
    edit(
        nested,
        "map/model.py",
        'kind="actor", container="outside"',
        'kind="actor", container="outside", map="style.py"',
    )
    assert run("--root", str(nested), "check") == 1
    assert (
        "placement: User is an actor and opens a map (style.py). An actor has no source modules"
        in capsys.readouterr().out
    )
    edit(
        nested,
        "map/gateway.py",
        'entry="create_app", region="serve"',
        'entry="create_app", region="serve", map="model.py"',
    )
    assert run("--root", str(nested), "check") == 2
    err = capsys.readouterr().err
    assert (
        "map/gateway.py: App opens map/model.py, which is already a parent map (map/model.py -> map/gateway.py). A map cannot open itself."
        in err
    )
    edit(nested, "map/gateway.py", 'map="model.py"', 'map="nowhere.py"')
    assert run("--root", str(nested), "check") == 2
    assert "map/gateway.py: App opens map/nowhere.py, which is missing" in capsys.readouterr().err


def test_pages_are_written_per_map_with_the_links_up_and_down(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--root", str(nested), "refresh") == 0
    top = (nested / "docs/map/index.html").read_text()
    gateway = (nested / "docs/map/Gateway/index.html").read_text()
    style = (nested / "docs/map/Style/index.html").read_text()
    assert "<title>demo system map</title>" in top
    assert "<title>demo system map: Gateway</title>" in gateway
    # The header counts the cards that are code, then the actors apart.
    assert "System map: 4 components and 1 actor, 4 flows, four layers." in top
    assert "System map: 3 components and 2 actors, 4 flows, four layers." in gateway
    # The top page: the mark on the opening cards, the legend row, the
    # links down in the header, and in the panel's detail the path of each
    # map inside and its preview (the sub-map's Structure reading, drawn
    # under an id of its own, every card and no edge).
    assert top.count('class="node__map"') == 2
    assert "stacked card opens a child map" in top
    assert (
        '<summary>Child maps</summary><a href="Gateway/index.html">Gateway</a>, <a href="Style/index.html">Style</a>'
        in top
    )
    assert (
        '"map":{"name":"Gateway","href":"Gateway/index.html","cards":3,'
        '"preview":"<svg id=\\"preview-Gateway\\"' in top
    )
    assert (
        '"map":{"name":"Style","href":"Style/index.html","cards":2,'
        '"preview":"<svg id=\\"preview-Style\\"' in top
    )
    assert '"map":null' in top
    assert "Map inside: <b>" in top and "systemap-f__opens" in top
    preview = json.loads(_detail_json(top))["Gateway"]["map"]["preview"]
    assert preview.startswith('<svg id="preview-Gateway"') and preview.endswith("</svg>")
    assert preview.count('class="node ') == 5 and 'class="flow ' not in preview
    assert 'data-id="App"' in preview and 'data-id="Routes"' in preview
    assert "#preview-Gateway .node" in preview and "#schematic" not in preview
    # The button and the overlay: the button's text once in the panel script,
    # the overlay once on a page with a map inside, and not on a page without.
    assert top.count(">Open map</button>") == 1
    assert top.count('id="submap"') == 1 and 'data-here="demo"' in top
    assert 'id="submapframe"' in top and 'src="about:blank"' in top
    assert "Double-click a card that opens a map" in top
    assert 'id="submap"' not in gateway and ">Open map</button>" in gateway
    assert "Double-click a card that opens a map" not in gateway
    # A sub-page: the component that contains the map., the link up, no mark, the model file it came from.
    assert '<h1><a href="../index.html">demo</a> / Gateway</h1>' in gateway
    assert 'class="node__map"' not in gateway and "Maps inside" not in gateway
    assert "<code>map/gateway.py</code>" in gateway
    assert 'data-id="App"' in gateway and 'data-id="Writer"' not in gateway
    assert 'data-id="Cache"' in style and 'data-id="App"' not in style
    # render --check covers every page; a missing sub-page is stale.
    assert run("--root", str(nested), "render", "--check") == 0
    assert "docs/map/Gateway/index.html agrees with the rendered output." in capsys.readouterr().out
    (nested / "docs/map/Style/index.html").unlink()
    assert run("--root", str(nested), "render", "--check") == 1
    out = capsys.readouterr().out
    assert "docs/map/Style/index.html is stale" in out and out.rstrip().endswith(
        "run: systemap refresh"
    )
    assert run("--root", str(nested), "check") == 1
    assert "docs/map/Style/index.html has no rendered output." in capsys.readouterr().out


def _detail_json(html: str) -> str:
    """The detail JSON the page inlines for the map's script."""
    start = html.index("var DETAIL = ") + len("var DETAIL = ")
    end = html.index(";\nvar PAL = ", start)
    return html[start:end].replace("<\\/", "</")


@needs_node
def test_the_map_inside_a_card_opens_in_place(nested: Path) -> None:
    """The Node driver: the panel's preview and button; the button, a
    double-click and a second Enter open the overlay; Escape and the close
    control close it and hand the focus back to the opener, the selection
    kept; a card without a map is left alone by the same keys."""
    assert run("--root", str(nested), "refresh") == 0
    args = [
        shutil.which("node") or "node",
        str(DRIVER),
        str(nested / "docs/map/index.html"),
        "--scenario",
        "submap",
    ]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    report: dict[str, Any] = json.loads(proc.stdout)
    # The first opening card in reading order, whichever place put on top.
    card = report["id"]
    inside = {"Gateway": (3, 5), "Style": (2, 4)}[card]  # cards of its own, cards drawn
    assert report["href"] == f"{card}/index.html"
    assert report["here"] == "demo" and report["overlays"] == 1
    has = report["panelHas"]
    assert has["opens"] == f"Map inside: {card} ({inside[0]} cards)"
    assert has["preview"] is True and has["previewId"] == f"preview-{card}"
    assert has["previewCards"] == inside[1] and has["previewInert"] is True
    assert has["buttons"] == 1 and has["buttonText"] == "Open map"
    assert has["links"] == 0, "the panel opens the map in place; no link out"
    steps = {s["label"]: s for s in report["steps"]}
    closed = {"overlayHidden": True, "src": "about:blank", "bodyClass": ""}
    for label in ("start", "selected", "escape", "close-control", "enter-once", "escape-again"):
        assert {k: steps[label][k] for k in closed} == closed, label
    opened = {
        "overlayHidden": False,
        "src": f"{card}/index.html",
        "crumb": f"demo > {card}",
        "focus": card,
        "active": "submapclose",
        "bodyClass": "submap-open",
    }
    for label in ("button", "dblclick", "enter-twice"):
        assert {k: steps[label][k] for k in opened} == opened, label
    assert report["escapePrevented"] is True
    for label in ("escape", "close-control", "escape-again"):
        assert steps[label]["focus"] == card, f"{label}: the selection is kept"
    assert steps["escape"]["activeIsOpenButton"], "focus returns to the Open map button"
    for label in ("close-control", "escape-again"):
        assert steps[label]["active"] == card, f"{label}: focus returns to the opening card"
    assert steps["escape-clears"]["focus"] == "", "a second Escape clears the selection"
    plain = steps["plain-enter-twice"]
    assert plain["focus"] == report["plainId"] and plain["overlayHidden"] is True


def test_figure_draws_one_map_by_id(nested: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = nested / "fig.html"
    assert (
        run("--root", str(nested), "figure", "--map", "Gateway", "--static", "--out", str(out)) == 0
    )
    text = out.read_text()
    assert 'data-id="App"' in text and 'data-id="Routes"' in text and 'data-id="Writer"' not in text
    assert "Inside Gateway: This figure shows the system map." in text
    assert 'class="node__map"' not in text
    assert (
        run(
            "--root",
            str(nested),
            "figure",
            "--map",
            "Style",
            "--layer",
            "control",
            "--out",
            str(out),
        )
        == 0
    )
    text = out.read_text()
    assert "Inside Style: Control flow: Which components cause other components to act?" in text
    assert "The page at <code>docs/map/Style/index.html</code>" in text
    # The top map by default: the mark, the legend row, the panel names the map without a link.
    assert run("--root", str(nested), "figure", "--interactive", "--out", str(out)) == 0
    text = out.read_text()
    assert text.count('class="node__map"') == 2 and "opens a map" in text
    assert '"map":{"name":"Gateway","href":"","cards":3,"preview":""}' in text
    capsys.readouterr()
    assert run("--root", str(nested), "figure", "--map", "Nope", "--out", str(out)) == 2
    assert "unknown map id: Nope. The nested map IDs are Gateway, Style" in capsys.readouterr().err
    # A configured figure of a sub-map is refreshed and checked like any other.
    (nested / "systemap.toml").write_text(
        CONFIG
        + '\n[[figures]]\nout = "figures/gateway.svg"\nmode = "system"\ninteractive = false\nmap = "Gateway"\n'
    )
    assert run("--root", str(nested), "refresh") == 0
    svg = (nested / "docs/map/figures/gateway.svg").read_text()
    assert svg.startswith("<svg ") and 'data-id="App"' in svg
    assert run("--root", str(nested), "check") == 0
    (nested / "systemap.toml").write_text(
        CONFIG + '\n[[figures]]\nout = "figures/x.svg"\nmap = "Nope"\n'
    )
    assert run("--root", str(nested), "check") == 2


def test_place_writes_into_a_sub_maps_file(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--root", str(nested), "refresh") == 0
    placed = (nested / "map/style.py").read_text()
    assert "x=" in placed and "y=" in placed
    # Strip the Style map's positions: place writes them again, the same.
    (nested / "map/style.py").write_text(STYLE.lstrip("\n"))
    capsys.readouterr()
    assert run("--root", str(nested), "place", "--print") == 0
    out = capsys.readouterr().out
    assert (
        f"place: 0 components placed, 5 kept (already positioned): {place.NOTHING_TO_PLACE}" in out
    )
    assert (
        "Style: place: 4 components placed, 0 kept. The command set all boxes and the canvas."
        in out
    )
    assert "Style:   Cache: x=" in out
    assert run("--root", str(nested), "place") == 0
    out = capsys.readouterr().out
    assert (
        "Style: place: The command wrote map/style.py: 4 components placed, 0 kept. The command set all boxes and the canvas"
        in out
    )
    assert "Gateway: place: wrote" not in out
    assert out.rstrip().endswith("run: systemap check")
    assert (nested / "map/style.py").read_text() == placed
    assert run("--root", str(nested), "check") == 0


def test_judgement_and_describe_lines_carry_the_maps_id(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--root", str(nested), "judgement") == 0
    out = capsys.readouterr().out
    assert "  single module: Reader contains only pkg.reader\n" in out
    assert "  Gateway: single module: App contains only pkg.gateway.app\n" in out
    assert "  Style: single module: Compiler contains only pkg.style.compiler\n" in out
    assert "  Gateway: thin layer: data shows 2 components" not in out
    # The crossing import from the gateway routes into the style cache is
    # the top map's question (Gateway -> Style has a flow) and not the sub-map's.
    assert "crossing import" not in out
    # A kind answer covers every map; an item answer quotes the line as printed.
    (nested / "systemap.toml").write_text(
        CONFIG + "\n[judgement]\nanswered = [\n"
        '  { kind = "single module", policy = true, reason = "small parts" },\n'
        '  { item = "Gateway: thin layer: data shows 2 components", reason = "one record" },\n'
        '  { item = "thin layer: control shows 0 components", reason = "stale on purpose" },\n'
        "]\n"
    )
    assert run("--root", str(nested), "judgement") == 0
    out = capsys.readouterr().out
    assert "  single module:" not in out
    assert "  Gateway: single module:" not in out
    assert "Gateway: thin layer: data" in out
    assert "stale answer:" in out
    assert "stale answer: 'thin layer: control shows 0 components' is now missing." in out
    assert run("--root", str(nested), "describe") == 0
    out = capsys.readouterr().out
    assert out.startswith("canvas ")
    assert "\nGateway: canvas " in out and "\nStyle: canvas " in out
    assert "Gateway: regions: The component counts follow.\nGateway:   serve: 3 components (" in out
    assert "Style: positions: 0 pinned, 4 placed" in out


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def test_the_page_names_the_commit_the_facts_are_from(nested: Path) -> None:
    """The facts record HEAD at extraction, one commit before the one that
    records them; the page calls the sha what it is, on every map's page."""
    git(nested, "init", "-q")
    git(nested, "add", "-A")
    git(nested, "commit", "-q", "-m", "base")
    sha = git(nested, "rev-parse", "HEAD")
    assert run("--root", str(nested), "refresh") == 0
    for rel in ("index.html", "Gateway/index.html"):
        html = (nested / "docs/map" / rel).read_text()
        assert (
            f'<p>HEAD at extraction: <code title="HEAD at extraction of the working tree">{sha[:10]}</code>.</p>'
            in html
        ), rel
        assert "Stored source data" in html
        assert "This page cannot detect subsequent changes." in html
        assert "Extraction reads the working tree, which can contain uncommitted changes." in html
        assert "Built at" not in html, rel
    # The field table the facts view and the skill's schema read says the same.
    from systemap.extract import FIELDS

    assert (
        "facts",
        "built_at_commit",
        "The commit read during extraction (`HEAD`), or empty outside Git. "
        "The page prints `facts from <sha>`. Extraction precedes the commit recording facts",
    ) in FIELDS


def test_delta_names_the_card_and_the_map_a_moved_module_belongs_to(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(nested, "init", "-q")
    git(nested, "add", "-A")
    git(nested, "commit", "-q", "-m", "base")
    (nested / "pkg/gateway/store.py").rename(nested / "pkg/gateway/db.py")
    edit(nested, "pkg/gateway/app.py", "pkg.gateway.store", "pkg.gateway.db")
    write_tree(nested, {"pkg/style/extra.py": "def extra() -> int:\n    return 1\n"})
    git(nested, "add", "-A")
    git(nested, "commit", "-q", "-m", "head")
    assert run("--root", str(nested), "delta", "--base", "HEAD~1") == 1
    out = capsys.readouterr().out
    # The top map: the pattern claims the new path, nothing to do there.
    assert (
        "  moved: pkg.gateway.store -> pkg.gateway.db (same content), with a claim in Gateway\n"
        in out
    )
    assert "  added: pkg.style.extra, with a claim in Style\n" in out
    # The map inside Gateway: its Store card names the old path, in its own file.
    assert (
        "  Gateway: moved: pkg.gateway.store -> pkg.gateway.db (same content). Store specifies "
        "pkg.gateway.store in implemented_by. Change this claim to pkg.gateway.db in map/gateway.py\n"
    ) in out
    # The map inside Style: the new module has no card there, and no ignore can excuse it.
    assert (
        "  Style: added: pkg.style.extra, No component has a claim for it. "
        "Add it to a component implemented_by in map/style.py, "
        "the map inside Style has the same module claims as Style\n"
    ) in out
    assert "A decision is necessary (" in out
    assert "source review:" in out
    assert "4 of 9 components specified" in out
    assert run("--root", str(nested), "delta", "--base", "HEAD~1", "--format", "markdown") == 1
    assert "- `Gateway: moved: pkg.gateway.store -> pkg.gateway.db" in capsys.readouterr().out


def test_suggest_reads_the_tree_from_the_command(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--root", str(nested), "suggest") == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith(
        "nesting: no map has more than 40 components and no component has more than 10 modules. No nested map is necessary."
    )
