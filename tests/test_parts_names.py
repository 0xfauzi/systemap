"""The file name of a nested map: one function for `suggest` and for later part commands.

Acceptance values:

1. `parts.file_name` gives the map ID in lower case, with `_` in place of each `/`, and
   `.py`. The map `Gateway/Routes` gives `gateway_routes.py`.
2. `suggest` prints `map="<file name>"` with the same function, also for a nested map.
   Before the change, it printed `map="map/<card>.py"`, which is `map/map/<card>.py`
   relative to the default model file.
3. A level-2 nested map at the file name loads in `nest.load`, beside the top model.
"""

from __future__ import annotations

from pathlib import Path

from conftest import write_tree
from test_nested import CONFIG, GATEWAY, MODELS, TREE
from test_suggest_nesting import _model

from systemap import config, nest, parts, suggest

ROUTES = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="routes", label="ROUTES", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="serve", label="SERVE", box=(0, 0, 0, 0), container="routes"),)
COMPONENTS = (
    Component(id="App", does="The card that calls in.", kind="actor", container="around"),
    Component(id="Style", does="The card the route reaches.", kind="actor", container="around"),
    Component(id="Route", does="Dispatches a path.", implemented_by=("pkg.gateway.routes",), entry="route", region="serve"),
)
FLOWS = (Flow("App", "Route", "dispatch", "control"), Flow("Route", "Style", "guide lookup", "data"))
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"App": "the app", "Style": "the guides", "Route": "the route"},
    relations={
        ("App", "Route"): "The app dispatches the path to the route.",
        ("Route", "Style"): "The route looks a guide up in the cache.",
    },
)
"""


def test_the_file_name_is_the_lower_case_map_id() -> None:
    """Acceptance 1."""
    assert parts.file_name("Gateway") == "gateway.py"
    assert parts.file_name("Gateway/Routes") == "gateway_routes.py"
    assert parts.map_id("", "Gateway") == "Gateway"
    assert parts.map_id("Gateway", "Routes") == "Gateway/Routes"


def test_suggest_prints_the_file_name_of_the_function() -> None:
    """Acceptance 2, for a card in a nested map."""
    model, meaning, facts = _model({f"C{i}": (12 if i < 1 else 1) for i in range(41)})
    m = nest.Map("Gateway", Path("map/gateway.py"), "map/gateway.py", model, meaning, {})
    lines = suggest.nesting_lines(nest.Tree((m,)), facts)  # type: ignore[arg-type]
    name = parts.file_name("Gateway/C0")
    assert lines[1] == f'  C0: 12 modules, map="{name}"'
    assert name == "gateway_c0.py"


def test_a_nested_map_at_the_file_name_loads(tmp_path: Path) -> None:
    """Acceptance 3: the name from the function is a correct `map=` value at level 2."""
    name = parts.file_name("Gateway/Routes")
    gateway = GATEWAY.replace(
        'entry="route", region="serve")', f'entry="route", region="serve", map="{name}")'
    )
    assert gateway != GATEWAY
    files = {**TREE, "systemap.toml": CONFIG, **MODELS, "map/gateway.py": gateway}
    write_tree(tmp_path, {**files, f"map/{name}": ROUTES})
    tree = nest.load(config.load(tmp_path))
    assert tree.get("Gateway/Routes").path == tmp_path / "map" / name
    assert tree.get("Gateway").path.name == parts.file_name("Gateway")
