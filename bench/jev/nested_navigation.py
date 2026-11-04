"""Measure the navigation pages of a map tree with 3 levels: M12, M13 (axe-core part) and M15.

Acceptance (written before the run, from the design of the nested parts, section
"Measurements"):

- M12: the load of a nested page with 40 cards to an interactive map takes at most 1.5 s
  in Chromium and in Firefox. "Interactive" is the first animation frame in which the map
  script and the page script are ready (`svg#schematic.systemap` and `.page` exist). The
  time is `performance.now()` at that frame, from the start of the navigation. The script
  gives the median and the maximum of 5 loads, each in a new browser context.
- M13, axe-core part only: axe-core finds 0 serious or critical issues on a level-3 page,
  in Ink (`dark`) and in Paper (`light`). The tests with NVDA and VoiceOver are not part of
  this script.
- M15: on a phone of 360 x 740 CSS pixels, a level-3 page has no horizontal scroll, each
  visible tap target is 44 px or more in width and in height, and the page heading shows
  the last segment of the map path with no cut.

The fixture is a map tree that this script writes: the top map, `Gateway`,
`Gateway/Routes`, and the level-3 map `Gateway/Routes/Handlers` with 40 internal cards.
The script makes the pages with `systemap place`, `extract` and `refresh`.

A browser that Playwright cannot start gives "not run" and the reason. The script does not
put a value in place of a measurement that it cannot make. The axe-core file is not in the
repository: give its path in AXE_PATH. Without it, M13 is "not run".

Run from the repository root:

    NODE_PATH=/opt/node-tools/node_modules AXE_PATH=.../axe.min.js \\
      uv run python bench/jev/nested_navigation.py OUT_DIR
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from systemap.cli import main

CARDS = 40

CONFIG = """
name = "tree"
[package_roots]
"pkg" = "pkg"
"""

TOP = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (
    Container(id="outside", label="OUTSIDE", box=(0, 0, 0, 0), tone="host"),
    Container(id="system", label="SYSTEM", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="edge", label="EDGE", box=(0, 0, 0, 0), container="system"),)
COMPONENTS = (
    Component(id="User", does="Sends the requests.", kind="actor", container="outside"),
    Component(id="Front", does="Receives the requests.", implemented_by=("pkg.front",), entry="front", region="edge"),
    Component(id="Gateway", does="Sends each request to a handler.", implemented_by=("pkg.gw.*",), entry="app", region="edge", map="gateway.py"),
)
FLOWS = (Flow("User", "Front", "request", "data"), Flow("Front", "Gateway", "request", "control"))
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"User": "the person", "Front": "the front", "Gateway": "the gateway"},
    relations={("User", "Front"): "The user sends a request.", ("Front", "Gateway"): "The front starts the gateway."},
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
    Component(id="Front", does="Starts the gateway.", kind="actor", container="around"),
    Component(id="App", does="Starts the routes.", implemented_by=("pkg.gw.app",), entry="app", region="serve"),
    Component(id="Routes", does="Finds the handler.", implemented_by=("pkg.gw.rt.*",), entry="table", region="serve", map="gateway_routes.py"),
)
FLOWS = (Flow("Front", "App", "request", "control"), Flow("App", "Routes", "path", "data"))
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"Front": "the front", "App": "the app", "Routes": "the routes"},
    relations={("Front", "App"): "The front starts the app.", ("App", "Routes"): "The app gives the path."},
)
"""

ROUTES = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="routes", label="ROUTES", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="find", label="FIND", box=(0, 0, 0, 0), container="routes"),)
COMPONENTS = (
    Component(id="App", does="Gives the path.", kind="actor", container="around"),
    Component(id="Table", does="Keeps the routes.", implemented_by=("pkg.gw.rt.table",), entry="table", region="find"),
    Component(id="Handlers", does="Operate on the requests.", implemented_by=("pkg.gw.rt.h.*",), entry="h00", region="find", map="gateway_routes_handlers.py"),
)
FLOWS = (Flow("App", "Table", "path", "data"), Flow("Table", "Handlers", "request", "control"))
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"App": "the app", "Table": "the table", "Handlers": "the handlers"},
    relations={("App", "Table"): "The app gives the path.", ("Table", "Handlers"): "The table starts a handler."},
)
"""


def handlers() -> str:
    """Give the level-3 model: the actor Table and 40 handlers in 4 regions, one flow chain."""
    regions = ", ".join(
        f'Region(id="r{k}", label="PART {k + 1}", box=(0, 0, 0, 0), container="handlers")'
        for k in range(4)
    )
    cards = "\n".join(
        f'    Component(id="H{i:02d}", does="Operates on part {i} of a request.", '
        f'implemented_by=("pkg.gw.rt.h.m{i:02d}",), entry="h{i:02d}", region="r{i % 4}"),'
        for i in range(CARDS)
    )
    pairs = [("Table", "H00")] + [(f"H{i:02d}", f"H{i + 1:02d}") for i in range(CARDS - 1)]
    flows = "\n".join(f'    Flow("{a}", "{b}", "request", "data"),' for a, b in pairs)
    plain = {"Table": "the table"} | {f"H{i:02d}": f"handler {i}" for i in range(CARDS)}
    relations = ", ".join(f'("{a}", "{b}"): "{a} gives the request to {b}."' for a, b in pairs)
    return (
        "from systemap import Component, Container, Flow, Meaning, Model, Region\n\n"
        "CONTAINERS = (\n"
        '    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),\n'
        '    Container(id="handlers", label="HANDLERS", box=(0, 0, 0, 0), tone="server"),\n)\n'
        f"REGIONS = ({regions},)\n"
        "COMPONENTS = (\n"
        '    Component(id="Table", does="Starts a handler.", kind="actor", container="around"),\n'
        f"{cards}\n)\n"
        f"FLOWS = (\n{flows}\n)\n"
        "MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, "
        "components=COMPONENTS, flows=FLOWS, flow_kinds=())\n"
        f"MEANING = Meaning(plain={json.dumps(plain)}, relations={{{relations}}})\n"
    )


def sources() -> dict[str, str]:
    files = {
        "pkg/__init__.py": "",
        "pkg/front.py": "def front() -> None:\n    pass\n",
        "pkg/gw/__init__.py": "",
        "pkg/gw/app.py": "def app() -> None:\n    pass\n",
        "pkg/gw/rt/__init__.py": "",
        "pkg/gw/rt/table.py": "def table() -> None:\n    pass\n",
        "pkg/gw/rt/h/__init__.py": "",
    }
    for i in range(CARDS):
        files[f"pkg/gw/rt/h/m{i:02d}.py"] = f"def h{i:02d}() -> None:\n    pass\n"
    return files


def write(root: Path) -> None:
    files = sources() | {
        "systemap.toml": CONFIG,
        "map/model.py": TOP,
        "map/gateway.py": GATEWAY,
        "map/gateway_routes.py": ROUTES,
        "map/gateway_routes_handlers.py": handlers(),
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def make(root: Path) -> None:
    """Write the fixture and its pages. A command that fails stops the script."""
    if root.exists():
        # Remove only an earlier fixture of this script, never another folder.
        mark = root / "systemap.toml"
        if not mark.is_file() or mark.read_text(encoding="utf-8") != textwrap.dedent(CONFIG).lstrip(
            "\n"
        ):
            raise SystemExit(
                f"{root} exists and is not a fixture of this script. Give a new folder."
            )
        shutil.rmtree(root)
    write(root)
    for command in ("place", "extract", "refresh"):
        code = main(["--root", str(root), command])
        if code != 0:
            raise SystemExit(f"systemap {command} exited {code}. The measurement did not run.")


def browse(root: Path) -> dict[str, object]:
    script = Path(__file__).with_name("nested_navigation.js")
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node is not available. The measurement did not run.")
    page = root / "docs/map/Gateway/Routes/Handlers/index.html"
    proc = subprocess.run(
        [node, str(script), str(page), os.environ.get("AXE_PATH", "")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"The browser script failed:\n{proc.stderr}")
    report: dict[str, object] = json.loads(proc.stdout)
    return report


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bench/scratch/nested_navigation")
    make(out)
    print(json.dumps(browse(out), indent=2))
