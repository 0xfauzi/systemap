"""A tree of nested maps on three levels below the top map, for tests and measurements.

The top map has the component Base and the components P0, P1, and so on. Each P card
opens a map on level 1. That map has the component Glue and the components Q0, Q1, and
so on. Each Q card opens a map on level 2 with the components R0 and Deep. Each Deep card
opens a map on level 3 with the components D0 and D1.

The module of each R0 imports the module of the top card Base. Thus a nested map on
level 2 imports a module of a sibling card of the top map. The maps on level 1 and level
2 have the actor Base for it, because the actors of a nested map must be components of
its parent map.

With the default sizes, the tree has 11 maps: 1 + parts + 2 * parts * subs.
"""

from __future__ import annotations

from systemap import parts as parts_mod

CONFIG = """
name = "three levels"
[package_roots]
"pkg" = "pkg"
"""

HEAD = "from systemap import Component, Container, Flow, Meaning, Model, Region\n"
TAIL = (
    "MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, "
    "components=COMPONENTS, flows=FLOWS, flow_kinds=())\n"
)


def map_count(parts: int = 2, subs: int = 2) -> int:
    """Give the number of maps that `files` makes, with the top map."""
    return 1 + parts + 2 * parts * subs


def files(parts: int = 2, subs: int = 2) -> dict[str, str]:
    """Give the source files, the configuration, and the model file of each map."""
    out = {"systemap.toml": CONFIG, "map/model.py": _top(parts), **_source(parts, subs)}
    for i in range(parts):
        out[f"map/{_file(f'P{i}')}"] = _level_1(i, subs)
        for j in range(subs):
            out[f"map/{_file(f'P{i}/Q{j}')}"] = _level_2(i, j)
            out[f"map/{_file(f'P{i}/Q{j}/Deep')}"] = _level_3(i, j)
    return out


def map_ids(parts: int = 2, subs: int = 2) -> list[str]:
    """Give the ID of each map in the order of `nest.load`, with "" for the top map."""
    out = [""]
    for i in range(parts):
        out.append(f"P{i}")
        for j in range(subs):
            out += [f"P{i}/Q{j}", f"P{i}/Q{j}/Deep"]
    return out


def _file(map_id: str) -> str:
    return parts_mod.file_name(map_id)


def _source(parts: int, subs: int) -> dict[str, str]:
    out = {
        "pkg/__init__.py": "",
        "pkg/base/__init__.py": "",
        "pkg/base/util.py": "def value(key: str) -> str:\n    return key\n",
    }
    for i in range(parts):
        calls = (
            "".join(f"from pkg.p{i}.q{j}.r0 import run_{i}_{j}\n" for j in range(subs))
            + f"\n\ndef start_{i}() -> None:\n"
        )
        calls += "".join(f"    run_{i}_{j}()\n" for j in range(subs))
        out[f"pkg/p{i}/__init__.py"] = ""
        out[f"pkg/p{i}/glue.py"] = calls
        for j in range(subs):
            base = f"pkg/p{i}/q{j}"
            out[f"{base}/__init__.py"] = ""
            out[f"{base}/deep/__init__.py"] = ""
            out[f"{base}/r0.py"] = (
                "from pkg.base.util import value\n"
                f"from pkg.p{i}.q{j}.deep.d0 import work_{i}_{j}\n\n\n"
                f"def run_{i}_{j}() -> str:\n    return work_{i}_{j}(value('k'))\n"
            )
            out[f"{base}/deep/d0.py"] = (
                f"from pkg.p{i}.q{j}.deep.d1 import detail_{i}_{j}\n\n\n"
                f"def work_{i}_{j}(key: str) -> str:\n    return detail_{i}_{j}(key)\n"
            )
            out[f"{base}/deep/d1.py"] = f"def detail_{i}_{j}(key: str) -> str:\n    return key\n"
    return out


def _card(cid: str, does: str, claims: str, entry: str, opens: str = "") -> str:
    where = f', map="{opens}"' if opens else ""
    return (
        f'    Component(id="{cid}", does="{does}", implemented_by=("{claims}",), '
        f'entry="{entry}", region="work"{where}),\n'
    )


def _actor(cid: str) -> str:
    return f'    Component(id="{cid}", does="An adjacent component.", kind="actor", container="around"),\n'


def _model(name: str, cards: list[str], flows: list[tuple[str, str, str, str]]) -> str:
    """Give the text of a model file with one container for the actors and one region."""
    ids = [card.split('"')[1] for card in cards]
    flow_rows = "".join(
        f'    Flow("{a}", "{b}", "{art}", "{kind}"),\n' for a, b, art, kind in flows
    )
    plain = ", ".join(f'"{cid}": "the {cid.lower()} part"' for cid in ids)
    relations = "".join(
        f'        ("{a}", "{b}"): "{a} sends the {art} to {b}.",\n' for a, b, art, _kind in flows
    )
    return (
        HEAD
        + "CONTAINERS = (\n"
        + '    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),\n'
        + f'    Container(id="part", label="{name.upper()}", box=(0, 0, 0, 0), tone="server"),\n'
        + ")\n"
        + 'REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="part"),)\n'
        + "COMPONENTS = (\n"
        + "".join(cards)
        + ")\n"
        + "FLOWS = (\n"
        + flow_rows
        + ")\n"
        + TAIL
        + f"MEANING = Meaning(\n    plain={{{plain}}},\n    relations={{\n{relations}    }},\n)\n"
    )


def _top(parts: int) -> str:
    cards = [_card("Base", "Gives the values.", "pkg.base.*", "value")]
    cards += [
        _card(f"P{i}", "Does one part of the work.", f"pkg.p{i}.*", f"start_{i}", _file(f"P{i}"))
        for i in range(parts)
    ]
    flows = [(f"P{i}", "Base", "value lookup", "data") for i in range(parts)]
    return _model("system", cards, flows)


def _level_1(i: int, subs: int) -> str:
    cards = [_actor("Base"), _card("Glue", "Starts the work.", f"pkg.p{i}.glue", f"start_{i}")]
    cards += [
        _card(f"Q{j}", "Does one task.", f"pkg.p{i}.q{j}.*", f"run_{i}_{j}", _file(f"P{i}/Q{j}"))
        for j in range(subs)
    ]
    flows = [("Glue", f"Q{j}", "request", "control") for j in range(subs)]
    flows += [(f"Q{j}", "Base", "value lookup", "data") for j in range(subs)]
    return _model(f"p{i}", cards, flows)


def _level_2(i: int, j: int) -> str:
    deep = _file(f"P{i}/Q{j}/Deep")
    cards = [
        _actor("Glue"),
        _actor("Base"),
        _card("R0", "Runs the task.", f"pkg.p{i}.q{j}.r0", f"run_{i}_{j}"),
        _card("Deep", "Does the work.", f"pkg.p{i}.q{j}.deep.*", f"work_{i}_{j}", deep),
    ]
    flows = [
        ("Glue", "R0", "request", "control"),
        ("R0", "Deep", "key", "data"),
        ("R0", "Base", "value lookup", "data"),
    ]
    return _model(f"q{j}", cards, flows)


def _level_3(i: int, j: int) -> str:
    cards = [
        _actor("R0"),
        _card("D0", "Does the work.", f"pkg.p{i}.q{j}.deep.d0", f"work_{i}_{j}"),
        _card("D1", "Gives the detail.", f"pkg.p{i}.q{j}.deep.d1", f"detail_{i}_{j}"),
    ]
    flows = [("R0", "D0", "key", "data"), ("D0", "D1", "key", "data")]
    return _model("deep", cards, flows)
