"""The boundary lines of a nested map: `boundary flow` and `boundary import`.

Acceptance values:

1. A tree whose nested flows and imports agree with the parent flows gives no boundary
   line.
2. Each form of each kind gives its line: a nested flow to an actor with no parent flow,
   a nested flow from an actor with no parent flow, a parent flow to X and a parent flow
   from X with no nested flow, an import of a component that is not an actor, and an
   import with no flow to the actor.
3. An import across the boundary of a level-2 map has the owner of the nearest ancestor
   map that claims the module: a module of the top card Base gives the owner Base.
4. A line does not change when its import count changes. The count is in the row below
   the line and in the JSON fields.
5. An exact answer becomes stale (pending) when the parent flow changes. A change to a
   component that the line does not name does not change the evidence.
6. `judgement --json` gives `map_id`, `parent_flow`, `nested_flows`, and `import_pairs`
   for a boundary line, and null for other lines.
7. `kind = "boundary flow"` and `kind = "boundary import"` are accepted answers, and
   each kind has an explanation.
8. A run with `--map` gives the boundary lines of the selected map.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import three_levels
from conftest import write_tree

from systemap import config, explain, judgement, judgement_json, nest, nest_join
from systemap.cli import main
from systemap.config import Answer

CONFIG = """
name = "join"
[package_roots]
"pkg" = "pkg"
"""
SOURCE = {
    "pkg/__init__.py": "",
    "pkg/auth.py": "def token() -> str:\n    return 't'\n",
    "pkg/store.py": "def get() -> str:\n    return 's'\n",
    "pkg/log.py": "def write() -> None:\n    return None\n",
    "pkg/gateway/__init__.py": "",
    "pkg/gateway/routes.py": "from pkg.auth import token\n\n\ndef route() -> str:\n    return token()\n",
    "pkg/gateway/extra.py": "def more() -> str:\n    return 'm'\n",
    "pkg/gateway/views.py": "from pkg.store import get\n\n\ndef view() -> str:\n    return get()\n",
}
HEAD = "from systemap import Component, Container, Flow, Meaning, Model, Region\n"
TOP = (
    HEAD
    + """
CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="system", label="SYSTEM", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="system"),)
COMPONENTS = (
    Component(id="Gateway", does="Takes the requests.", implemented_by=("pkg.gateway.*",), entry="route", region="work", map="gateway.py"),
    Component(id="Auth", does="Gives the tokens.", implemented_by=("pkg.auth",), entry="token", region="work"),
    Component(id="Store", does="Keeps the records.", implemented_by=("pkg.store",), entry="get", region="work"),
    Component(id="Log", does="Writes the log.", implemented_by=("pkg.log",), entry="write", region="work"),
)
FLOWS = (
    Flow("Gateway", "Auth", "token", "data"),
    Flow("Gateway", "Store", "record", "data"),
)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"Gateway": "the gateway", "Auth": "the auth", "Store": "the store", "Log": "the log"},
    relations={
        ("Gateway", "Auth"): "The gateway sends the token to the auth.",
        ("Gateway", "Store"): "The gateway sends the record to the store.",
    },
)
"""
)
NESTED = (
    HEAD
    + """
CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="system", label="GATEWAY", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="system"),)
COMPONENTS = (
    Component(id="Auth", does="An adjacent component.", kind="actor", container="around"),
    Component(id="Store", does="An adjacent component.", kind="actor", container="around"),
    Component(id="Routes", does="Takes the routes.", implemented_by=("pkg.gateway.routes", "pkg.gateway.extra"), entry="route", region="work"),
    Component(id="Views", does="Shows the views.", implemented_by=("pkg.gateway.views",), entry="view", region="work"),
)
FLOWS = (
    Flow("Routes", "Auth", "token", "data"),
    Flow("Views", "Store", "record", "data"),
)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"Auth": "the auth", "Store": "the store", "Routes": "the routes", "Views": "the views"},
    relations={
        ("Routes", "Auth"): "The routes send the token to the auth.",
        ("Views", "Store"): "The views send the record to the store.",
    },
)
"""
)
TO_AUTH = '    Flow("Routes", "Auth", "token", "data"),\n'
TO_AUTH_SENTENCE = '        ("Routes", "Auth"): "The routes send the token to the auth.",\n'


def run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


def build(root: Path, top: str = TOP, nested: str = NESTED, **source: str) -> Path:
    files = {"systemap.toml": CONFIG, "map/model.py": top, "map/gateway.py": nested, **SOURCE}
    files.update({f"pkg/{name.replace('__', '/')}.py": text for name, text in source.items()})
    write_tree(root, files)
    assert run(root, "extract") == 0
    return root


def facts_of(root: Path) -> dict[str, Any]:
    cfg = config.load(root)
    found: dict[str, Any] = json.loads(cfg.facts_path.read_text(encoding="utf-8"))
    return found


def boundary(root: Path) -> list[str]:
    cfg = config.load(root)
    tree = nest.load(cfg)
    lines = judgement_json.current_lines(tree, facts_of(root), cfg)
    return [line for line in lines if judgement.kind_of(line) in nest_join.KINDS]


def test_a_tree_that_agrees_gives_no_boundary_line(tmp_path: Path) -> None:
    """Acceptance 1."""
    assert boundary(build(tmp_path)) == []


def test_the_three_levels_fixture_gives_no_boundary_line(tmp_path: Path) -> None:
    """Acceptance 1, on three levels."""
    write_tree(tmp_path, three_levels.files())
    assert run(tmp_path, "extract") == 0
    assert boundary(tmp_path) == []


def test_a_nested_flow_with_no_parent_flow(tmp_path: Path) -> None:
    """Acceptance 2: the two directions of a nested flow with an actor."""
    nested = NESTED.replace(
        '    Component(id="Routes"',
        '    Component(id="Log", does="An adjacent component.", kind="actor", container="around"),\n'
        '    Component(id="Routes"',
    ).replace(
        TO_AUTH,
        TO_AUTH
        + '    Flow("Routes", "Log", "entry", "data"),\n    Flow("Auth", "Views", "key", "data"),\n',
    )
    nested = nested.replace(
        TO_AUTH_SENTENCE,
        TO_AUTH_SENTENCE
        + '        ("Routes", "Log"): "The routes send the entry to the log.",\n'
        + '        ("Auth", "Views"): "The auth sends the key to the views.",\n',
    )
    assert boundary(build(tmp_path, nested=nested)) == [
        "Gateway: boundary flow: Routes sends to actor Log, and the parent map has no flow "
        "from Gateway to Log",
        "Gateway: boundary flow: actor Auth sends to Views, and the parent map has no flow "
        "from Auth to Gateway",
    ]


def test_a_parent_flow_with_no_nested_flow(tmp_path: Path) -> None:
    """Acceptance 2: the two directions of a parent flow, and an import with no flow."""
    top = TOP.replace(
        '    Flow("Gateway", "Store", "record", "data"),\n',
        '    Flow("Gateway", "Store", "record", "data"),\n    Flow("Log", "Gateway", "entry", "data"),\n',
    ).replace(
        '        ("Gateway", "Store"): "The gateway sends the record to the store.",\n',
        '        ("Gateway", "Store"): "The gateway sends the record to the store.",\n'
        '        ("Log", "Gateway"): "The log sends the entry to the gateway.",\n',
    )
    nested = NESTED.replace(TO_AUTH, "").replace(TO_AUTH_SENTENCE, "")
    assert boundary(build(tmp_path, top=top, nested=nested)) == [
        "Gateway: boundary flow: the parent flow from Gateway to Auth has no nested flow to "
        "actor Auth",
        "Gateway: boundary flow: the parent flow from Log to Gateway has no nested flow from "
        "actor Log",
        "Gateway: boundary import: Routes imports Auth, and no flow connects Routes and actor Auth",
    ]


def test_an_import_of_a_component_that_is_not_an_actor(tmp_path: Path) -> None:
    """Acceptance 2."""
    views = "from pkg.log import write\n\n\ndef view() -> None:\n    return write()\n"
    root = build(tmp_path, gateway__views=views)
    assert boundary(root) == [
        "Gateway: boundary import: Views imports Log, and Log is not an actor of the map "
        "inside Gateway",
    ]


def level_2(root: Path, *, actor: bool) -> Path:
    files = three_levels.files(parts=1, subs=1)
    q0 = files["map/p0_q0.py"].replace('    Flow("R0", "Base", "value lookup", "data"),\n', "")
    q0 = q0.replace('        ("R0", "Base"): "R0 sends the value lookup to Base.",\n', "")
    if not actor:
        q0 = q0.replace(three_levels._actor("Base"), "")
    files["map/p0_q0.py"] = q0
    write_tree(root, files)
    assert run(root, "extract") == 0
    return root


def test_the_owner_comes_from_the_nearest_ancestor(tmp_path: Path) -> None:
    """Acceptance 3: R0 on level 2 imports a module of the top card Base."""
    root = level_2(tmp_path / "with", actor=True)
    assert boundary(root) == [
        "P0/Q0: boundary flow: the parent flow from Q0 to Base has no nested flow to actor Base",
        "P0/Q0: boundary import: R0 imports Base, and no flow connects R0 and actor Base",
    ]
    root = level_2(tmp_path / "without", actor=False)
    assert boundary(root) == [
        "P0/Q0: boundary flow: the parent flow from Q0 to Base has no nested flow to actor Base",
        "P0/Q0: boundary import: R0 imports Base, and Base is not an actor of the map inside Q0",
    ]


def evaluated(root: Path) -> tuple[judgement_json.Judged, nest.Tree, dict[str, Any]]:
    cfg = config.load(root)
    tree = nest.load(cfg)
    facts = facts_of(root)
    return judgement_json.evaluate(tree, facts, cfg), tree, facts


NO_FLOW = (
    "Gateway: boundary import: Routes imports Auth, and no flow connects Routes and actor Auth"
)
NO_NESTED = (
    "Gateway: boundary flow: the parent flow from Gateway to Auth has no nested flow to actor Auth"
)


def test_a_count_change_does_not_change_the_line(tmp_path: Path) -> None:
    """Acceptance 4 and 6."""
    nested = NESTED.replace(TO_AUTH, "").replace(TO_AUTH_SENTENCE, "")
    root = build(tmp_path, nested=nested)
    judged, tree, facts = evaluated(root)
    assert NO_FLOW in judged.lines
    assert judged.counts[NO_FLOW] == (1, "module")
    assert judged.detail(tree, facts, verbose=True)[NO_FLOW] == [
        "count: 1 module",
        "pkg.gateway.routes imports pkg.auth",
    ]
    extra = "from pkg.auth import token\n\n\ndef more() -> str:\n    return token()\n"
    write_tree(root, {"pkg/gateway/extra.py": extra})
    assert run(root, "extract") == 0
    judged, tree, facts = evaluated(root)
    assert NO_FLOW in judged.lines
    assert judged.counts[NO_FLOW] == (2, "module")
    row = next(r for r in judgement_json.payload(judged, {}, None)["open"] if r["line"] == NO_FLOW)
    assert row["count"] == 2
    assert row["map_id"] == "Gateway"
    assert row["parent_flow"] == {"src": "Gateway", "dst": "Auth", "artifacts": ["token"]}
    assert row["nested_flows"] == []
    assert row["import_pairs"] == [
        {"module": "pkg.gateway.extra", "imports": "pkg.auth"},
        {"module": "pkg.gateway.routes", "imports": "pkg.auth"},
    ]
    flow_row = next(
        r for r in judgement_json.payload(judged, {}, None)["open"] if r["line"] == NO_NESTED
    )
    assert flow_row["import_pairs"] == [] and flow_row["count"] is None
    other = next(
        r for r in judgement_json.payload(judged, {}, None)["open"] if r["kind"] == "single module"
    )
    assert [other[k] for k in ("map_id", "parent_flow", "nested_flows", "import_pairs")] == [
        None
    ] * 4


def test_an_exact_answer_is_stale_after_a_parent_flow_change(tmp_path: Path) -> None:
    """Acceptance 5."""
    nested = NESTED.replace(TO_AUTH, "").replace(TO_AUTH_SENTENCE, "")
    root = build(tmp_path, nested=nested)
    judged, _tree, _facts = evaluated(root)
    digest = judgement_json.digest(NO_NESTED, judged.evidence)
    assert digest is not None
    answer = Answer((NO_NESTED,), "The parent flow is a summary.", evidence=digest)
    assert NO_NESTED not in judgement.apply_answers(judged.lines, [answer], judged.evidence).open

    write_tree(root, {"map/model.py": TOP.replace('"Keeps the records."', '"Keeps all records."')})
    judged, _tree, _facts = evaluated(root)
    assert judgement_json.digest(NO_NESTED, judged.evidence) == digest

    changed = TOP.replace(
        'Flow("Gateway", "Auth", "token", "data")', 'Flow("Gateway", "Auth", "key", "data")'
    )
    write_tree(root, {"map/model.py": changed})
    judged, _tree, _facts = evaluated(root)
    assert NO_NESTED in judged.lines
    result = judgement.apply_answers(judged.lines, [answer], judged.evidence)
    assert NO_NESTED in result.open
    assert result.pending and "must have a new source review" in result.pending[0]


def test_kind_answers_and_explanations(tmp_path: Path) -> None:
    """Acceptance 7."""
    assert set(nest_join.KINDS) <= set(config.LINE_KINDS)
    for kind in nest_join.KINDS:
        lesson = explain.lesson(kind)
        assert lesson is not None and lesson.means and lesson.why and lesson.do
    nested = NESTED.replace(TO_AUTH, "").replace(TO_AUTH_SENTENCE, "")
    root = build(tmp_path, nested=nested)
    write_tree(
        root,
        {
            "systemap.toml": CONFIG
            + "[judgement]\nanswered = [\n"
            + '    { kind = "boundary flow", policy = true, reason = "A test." },\n'
            + '    { kind = "boundary import", policy = true, reason = "A test." },\n'
            + "]\n"
        },
    )
    judged, _tree, _facts = evaluated(root)
    assert NO_FLOW in judged.lines and NO_NESTED in judged.lines
    assert NO_FLOW not in judged.result.open and NO_NESTED not in judged.result.open


def test_a_scoped_run_gives_the_boundary_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 8."""
    nested = NESTED.replace(TO_AUTH, "").replace(TO_AUTH_SENTENCE, "")
    root = build(tmp_path, nested=nested)
    capsys.readouterr()
    run(root, "judgement", "--map", "Gateway", "--json")
    lines = [row["line"] for row in json.loads(capsys.readouterr().out)["open"]]
    assert NO_FLOW in lines and NO_NESTED in lines
    run(root, "judgement", "--map", ".", "--json")
    lines = [row["line"] for row in json.loads(capsys.readouterr().out)["open"]]
    assert not [line for line in lines if judgement.kind_of(line) in nest_join.KINDS]
