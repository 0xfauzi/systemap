"""Module roles in judgement: the units, the index, the lines, the evidence, the module
role answers, the flow source rule, the import crossing states, and the pipeline.

Acceptance values (section 19, stage 4a, of the module role specification):

1. `use_units` gives the unit of each imported name: the imported module, or the module
   of the same component that defines the name (with its `defined_as` name). A name that a
   module of a different component defines stays on the imported module, with a note. An
   import of the full module uses its call-site names, and keeps `"*"` for each of the
   five conditions of section 7.1a.
2. `index` gives the users, `used`, `star` and `provided` of each unit. An import only for
   type checks makes no user. A unit can have users in two maps. The line map is the
   deepest map that owns the module, or None in a scoped tree for a module of a sibling map.
3. `lines` gives the line form with the map prefix of the line map. `line_module` reads a
   module name with a space.
4. The evidence digest of a unit does not change for a new user, a move of the module, a
   new map claim, or a new function body. It changes for a new name, a new import, a new
   import form, and a new import by a string value.
5. `roles` gives each text of section 9.2, accepts the permitted answers, and neither
   accepts nor refuses an answer with a different digest. An inactive answer is not stale.
   `check_role` gives the same texts for one answer, and also the texts of the answer form.
6. The flow source rule refuses a helper answer for a cited unit, also through a facade,
   and a mixed answer whose cited name is not in `handoff`. It never refuses `handoff`.
7. `crossing_states` gives `open`, `waiting` and `closed` by section 10.1. In 200 random
   cases, each waiting import crossing has a unit with no module role and with a line. The
   fallback opens a waiting import crossing in a full tree when a unit has no line.
8. `evaluate` hides the waiting and closed crossing import lines, corrects the stale
   answers, and `blocking` is true for an open line, a refused answer, and a waiting
   import crossing in a run with `--map`. A run with `--map` and a full run accept the
   same module role answers and give the same states for the selected map.

The tests use recorded answers only. They call no decision provider and no agent.
"""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import (
    cli_scope,
    config,
    facts_file,
    judgement,
    judgement_json,
    module_use,
    nest,
    refused_answers,
)
from systemap.config import Answer
from systemap.model import Component, Flow, Meaning, Model

MEANING = Meaning(plain={})


def record(
    file: str,
    uses: dict[str, list[str]] | None = None,
    names: tuple[Any, ...] = (),
    **extra: Any,
) -> dict[str, Any]:
    """Give a module record with the keys that the rules read."""
    entries = [n if isinstance(n, dict) else {"name": n, "kind": "function"} for n in names]
    return {
        "file": file,
        "package": file.rpartition("/")[0],
        "uses": uses or {},
        "names": entries,
        **extra,
    }


def model(
    cards: dict[str, tuple[str, ...]],
    flows: tuple[Flow, ...] = (),
    opens: dict[str, str] | None = None,
) -> Model:
    found = opens or {}
    components = tuple(
        Component(id=c, does="It does a thing.", implemented_by=mods, map=found.get(c))
        for c, mods in cards.items()
    )
    return Model((800, 600), (), (), components, flows, ("data",))


def one_map(m: Model) -> nest.Tree:
    return nest.Tree((nest.Map("", Path("map/model.py"), "map/model.py", m, MEANING, {}),))


def owner(cards: dict[str, tuple[str, ...]]) -> dict[str, str]:
    return {module: card for card, mods in cards.items() for module in mods}


CARDS = {"A": ("app.a", "app.b"), "L": ("lib", "lib.h", "lib.mail"), "C": ("core.thing",)}


def base_components() -> dict[str, Any]:
    return {
        "app.a": record("app/a.py", {"lib.h": ["escape"]}),
        "app.b": record("app/b.py"),
        "lib": record(
            "lib/__init__.py",
            {"lib.mail": ["Mailer"], "core.thing": ["Thing"]},
            (
                {
                    "name": "Mailer",
                    "kind": "class",
                    "defined_in": "lib.mail",
                    "defined_as": "Mailer",
                },
                {
                    "name": "Sender",
                    "kind": "class",
                    "defined_in": "lib.mail",
                    "defined_as": "Mailer",
                },
                {
                    "name": "Thing",
                    "kind": "class",
                    "defined_in": "core.thing",
                    "defined_as": "Thing",
                },
            ),
        ),
        "lib.h": record("lib/h.py", names=("escape", "quote")),
        "lib.mail": record("lib/mail.py", names=("Mailer", "Other")),
        "core.thing": record("core/thing.py", names=("Thing",)),
    }


# ---- 1. use_units ----------------------------------------------------------------------


def test_use_units_of_names() -> None:
    comps = base_components()
    own = owner(CARDS)
    comps["app.a"]["uses"] = {"lib.h": ["escape"], "lib": ["Mailer", "Sender", "Thing"]}
    assert module_use.use_units(comps, own, "app.a", "lib.h") == {"lib.h": {"escape"}}
    # A re-export of the same component goes to the defining module, also with an alias.
    # A name that a module of a different component defines stays on the facade.
    assert module_use.use_units(comps, own, "app.a", "lib") == {
        "lib.mail": {"Mailer"},
        "lib": {"Thing"},
    }
    found = module_use.index(one_map(model(CARDS)), {"components": comps})
    assert found.units["lib"].notes == {"lib:Thing is defined in core.thing (C)."}


def site(**changes: Any) -> dict[str, Any]:
    found = {"bound": "import", "line": 1, "local": "h", "name": "*", "target": "lib.h"}
    found["uses"] = [[3, 4, "escape"], [5, 4, "quote"]]
    found.update(changes)
    return found


def test_a_full_module_import_uses_the_call_site_names() -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib.h": ["*"]}
    comps["app.a"]["call_sites"] = [site()]
    assert module_use.use_units(comps, owner(CARDS), "app.a", "lib.h") == {
        "lib.h": {"escape", "quote"}
    }


@pytest.mark.parametrize(
    "sites",
    [
        None,  # the adapter gives no call sites
        [],  # no record for the import
        [site(local="h.x")],  # a dotted local name
        [site(local="*")],
        [site(uses=[])],  # no rows
        [site(uses=[[3, 4, "escape"], [6, 1, ""]])],  # the module object as a value
    ],
)
def test_a_full_module_import_keeps_the_star(sites: list[dict[str, Any]] | None) -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib.h": ["*"]}
    if sites is not None:
        comps["app.a"]["call_sites"] = sites
    assert module_use.use_units(comps, owner(CARDS), "app.a", "lib.h") == {"lib.h": {"*"}}


# ---- 2. index ----------------------------------------------------------------------------


def test_the_index_gives_users_and_names() -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib.h": ["escape"], "lib": ["Mailer"]}
    comps["app.b"]["uses"] = {"lib.h": ["*"]}
    found = module_use.index(one_map(model(CARDS)), {"components": comps})
    unit = found.units["lib.h"]
    assert [(u.component, u.module, u.names) for u in unit.users] == [
        ("A", "app.a", ("escape",)),
        ("A", "app.b", ("*",)),
    ]
    assert unit.used == {"escape"} and unit.star
    assert unit.provided == {"escape", "quote"}
    assert unit.crossings == ["crossing import: A imports L and no flow connects them"]
    assert (unit.line_map, unit.component) == ("", "L")
    assert found.units["lib.mail"].used == {"Mailer"}
    crossing = found.crossings["crossing import: A imports L and no flow connects them"]
    assert crossing.units == {"lib.h": {"escape", "*"}, "lib.mail": {"Mailer"}}


def test_an_import_for_type_checks_makes_no_user() -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib.h": ["escape"], "lib.mail": ["Mailer"]}
    comps["app.a"]["import_forms"] = {"lib.mail": ["type"]}
    found = module_use.index(one_map(model(CARDS)), {"components": comps})
    assert "lib.mail" not in found.units and "lib.h" in found.units


NESTED = {"L1": ("lib.h",), "L2": ("lib.x",)}


def nested_tree(
    selected: str | None = None, sibling: bool = True
) -> tuple[nest.Tree, dict[str, Any]]:
    """A top map with A, L and S. L opens the nested map L. S opens the map S, which a
    scoped load of L does not load."""
    cards = {"A": ("app.a",), "L": ("lib.h", "lib.x"), "S": ("side.s",)}
    top = model(cards, opens={"L": "map/l.py", "S": "map/s.py"})
    inner = model(NESTED)
    side = model({"S1": ("side.s",)})
    maps = [
        nest.Map("", Path("map/model.py"), "map/model.py", top, MEANING, {}),
        nest.Map("L", Path("map/l.py"), "map/l.py", inner, MEANING, {}, parent="", card="L"),
    ]
    if sibling:
        maps.append(
            nest.Map("S", Path("map/s.py"), "map/s.py", side, MEANING, {}, parent="", card="S")
        )
    comps = {
        "app.a": record("app/a.py", {"lib.h": ["escape"]}),
        "lib.h": record("lib/h.py", names=("escape", "quote")),
        "lib.x": record("lib/x.py", {"lib.h": ["quote"], "side.s": ["run"]}),
        "side.s": record("side/s.py", names=("run",)),
    }
    return nest.Tree(tuple(maps), selected), {"components": comps}


def test_a_unit_with_users_in_two_maps_has_its_line_in_the_deepest_map() -> None:
    tree, facts = nested_tree()
    found = module_use.index(tree, facts)
    unit = found.units["lib.h"]
    assert sorted((u.map, u.component) for u in unit.users) == [("", "A"), ("L", "L2")]
    assert unit.used == {"escape", "quote"}
    assert (unit.line_map, unit.component, unit.prefix) == ("L", "L1", "L: ")
    assert found.units["side.s"].line_map == "S"


def test_the_line_map_of_a_sibling_module_is_none_in_a_scoped_tree() -> None:
    tree, facts = nested_tree(selected="L", sibling=False)
    found = module_use.index(tree, facts)
    assert found.units["side.s"].line_map is None
    assert found.units["lib.h"].line_map == "L"
    assert module_use.lines(found, tree) == [
        "L: module use: other components import lib.h and no flow connects them to its component"
    ]


# ---- 3. lines and line_module ------------------------------------------------------------


def test_the_line_form_and_the_module_of_a_line() -> None:
    tree, facts = nested_tree()
    found = module_use.index(tree, facts)
    assert module_use.lines(found, tree) == [
        "L: module use: other components import lib.h and no flow connects them to its component",
        "S: module use: other components import side.s and no flow connects them to its component",
    ]
    line = (
        "module use: other components import web/my page and no flow connects them to its component"
    )
    assert module_use.line_module(line) == "web/my page"
    assert module_use.item_module("Orm: " + line) == "web/my page"
    assert module_use.line_module("crossing import: A imports B and no flow connects them") is None
    assert judgement.kind_of("L: " + line) == "module use"


# ---- 4. evidence -------------------------------------------------------------------------


def digest_of(comps: dict[str, Any], cards: dict[str, tuple[str, ...]] = CARDS) -> str:
    found = module_use.index(one_map(model(cards)), {"components": comps})
    return module_use.evidence(found)["lib.h"]


def test_the_evidence_of_a_unit() -> None:
    before = digest_of(base_components())
    same = base_components()
    same["app.b"]["uses"] = {"lib.h": ["quote"]}  # a new user
    assert digest_of(same) == before
    moved = {
        "A": ("app.a", "app.b"),
        "L": ("lib", "lib.mail"),
        "H": ("lib.h",),
        "C": ("core.thing",),
    }
    assert digest_of(base_components(), moved) == before  # a move of the module
    body = base_components()
    body["lib.h"].update(source_sha256="1" * 64, syntax_sha="2" * 64, loc=99)  # a function body
    assert digest_of(body) == before
    claim = model({**CARDS})
    claim = dataclasses.replace(
        claim,
        components=tuple(dataclasses.replace(c, does="A new claim.") for c in claim.components),
    )
    found = module_use.index(one_map(claim), {"components": base_components()})
    assert module_use.evidence(found)["lib.h"] == before  # a new map claim
    for change in (
        {"names": [*base_components()["lib.h"]["names"], {"name": "strip", "kind": "function"}]},
        {"uses": {"core.thing": ["Thing"]}},
        {"dynamic_imports": [{"call": "import_module", "text": "x", "target": "", "line": 3}]},
    ):
        changed = base_components()
        changed["lib.h"].update(change)
        assert digest_of(changed) != before, change
    used = base_components()
    used["lib.h"]["uses"] = {"core.thing": ["Thing"]}
    formed = base_components()
    formed["lib.h"].update(uses={"core.thing": ["Thing"]}, import_forms={"core.thing": ["call"]})
    assert digest_of(formed) != digest_of(used)  # a new form of an import that stays


# ---- 5. roles ----------------------------------------------------------------------------

LINE_H = module_use.module_line("lib.h")


def picked(
    comps: dict[str, Any], *answers: Answer, flows: tuple[Flow, ...] = ()
) -> module_use.Roles:
    tree = one_map(model(CARDS, flows))
    facts = {"components": comps}
    found = module_use.index(tree, facts)
    return module_use.roles(answers, found, module_use.evidence(found), tree, facts)


def role(comps: dict[str, Any], item: str = LINE_H, **keys: Any) -> Answer:
    tree = one_map(model(CARDS))
    found = module_use.index(tree, {"components": comps})
    module = module_use.item_module(item) or ""
    evidence = module_use.evidence(found).get(module, "0" * 64)
    return Answer((item,), "a reason", evidence=keys.pop("evidence", evidence), **keys)


def texts(roles: module_use.Roles) -> list[str]:
    return [row["text"] for row in roles.refused]


def test_the_symbol_rule_texts() -> None:
    comps = base_components()
    for keys, text in (
        (
            {"role": "helper"},
            f"'{LINE_H}': role \"helper\" must have a symbol: a name from the rows below the line.",
        ),
        (
            {"role": "helper", "symbol": "quote"},
            f"'{LINE_H}': quote is not a name of lib.h that other components import. Give a "
            "name from the rows below the line.",
        ),
        ({"role": "handoff", "symbol": "nope"}, f"'{LINE_H}': nope is not a name of lib.h."),
        (
            {"role": "mixed", "handoff": ("escape", "nope")},
            f"'{LINE_H}': nope in handoff is not a name of lib.h.",
        ),
    ):
        found = picked(comps, role(comps, **keys))
        assert texts(found) == [text] and found.refused[0]["cause"] == "symbol"
        assert not found.accepted


def test_a_helper_answer_for_a_module_with_no_names() -> None:
    comps = base_components()
    comps["lib.h"]["names"] = []
    comps["app.a"]["uses"] = {"lib.h": ["*"]}
    assert set(picked(comps, role(comps, role="helper")).accepted) == {"lib.h"}
    found = picked(comps, role(comps, role="helper", symbol="escape"))
    assert texts(found) == [f"'{LINE_H}': the facts give no names for lib.h. Remove the symbol."]


def test_the_accepted_symbols() -> None:
    comps = base_components()
    comps["lib.h"]["names"] = []  # the symbol is only in used(M)
    assert set(picked(comps, role(comps, role="helper", symbol="escape")).accepted) == {"lib.h"}
    whole = base_components()
    whole["app.b"]["uses"] = {"lib.h": ["*"]}  # a user of the full module
    assert set(picked(whole, role(whole, role="helper", symbol="quote")).accepted) == {"lib.h"}
    assert set(picked(whole, role(whole, role="handoff")).accepted) == {"lib.h"}
    mixed = role(whole, "Sub: " + LINE_H, role="mixed", handoff=("quote",))
    assert set(picked(whole, mixed).accepted) == {"lib.h"}  # the map prefix does not matter


def test_a_pending_answer_is_neither_accepted_nor_refused() -> None:
    comps = base_components()
    found = picked(comps, role(comps, role="helper", symbol="nope", evidence="0" * 64))
    assert not found.accepted and not found.refused


def test_check_role_gives_the_text_of_one_refused_answer() -> None:
    """`check_role` applies the rules of the answer form and of `roles` to one answer."""
    comps = base_components()
    tree = one_map(model(CARDS, (flow("lib.h@abc"),)))
    facts = {"components": comps}
    found = module_use.index(tree, facts)
    digests = module_use.evidence(found)

    def check(entry: dict[str, Any]) -> str | None:
        given = {"item": LINE_H, "reason": "a test", **entry}
        return module_use.check_role(given, found, digests, tree, facts)

    assert check({"role": "handoff"}) is None
    assert (
        check({"role": "handoff", "symbol": "nope"}) == f"'{LINE_H}': nope is not a name of lib.h."
    )
    flow_text = str(check({"role": "helper", "symbol": "escape"}))
    assert flow_text.startswith(f"'{LINE_H}': the flow L -> C (a message) cites lib.h.")
    assert check({"role": "bad"}) == 'role must be "helper", "handoff", or "mixed".'
    pending = {"role": "handoff", "symbol": "nope", "evidence": "0" * 64}
    assert check(pending) is None  # a pending answer is not refused
    answer = role(comps, role="handoff", symbol="nope")
    assert module_use.check_role(answer, found, digests, tree, facts) == check(
        {"role": "handoff", "symbol": "nope"}
    )


def test_an_inactive_answer_is_not_stale() -> None:
    comps = base_components()
    tree = one_map(model(CARDS))
    found = module_use.index(tree, {"components": comps})
    inactive = module_use.module_line("app.b")  # in the facts, but not a unit
    gone = module_use.module_line("gone.module")  # not in the facts
    result = judgement.Answered([], 0, [inactive, gone])
    assert refused_answers.correct_stale(result, {}, found) == []
    assert result.stale == [gone] and result.unused == []


# ---- 6. the flow source rule -------------------------------------------------------------


def flow(ref: str) -> Flow:
    return Flow("L", "C", "a message", "data", source_refs=(ref,))


def test_a_flow_that_cites_the_module_refuses_a_helper_answer() -> None:
    comps = base_components()
    found = picked(comps, role(comps, role="helper", symbol="escape"), flows=(flow("lib.h@abc"),))
    assert texts(found) == [
        f"'{LINE_H}': the flow L -> C (a message) cites lib.h. Thus the map shows that lib.h "
        'takes part in a flow. Change the module role to "handoff" or "mixed".'
    ]
    assert found.refused[0]["cause"] == "flow_source"
    handoff = picked(comps, role(comps, role="handoff"), flows=(flow("lib.h@abc"),))
    assert set(handoff.accepted) == {"lib.h"} and not handoff.refused


def test_a_flow_that_cites_a_re_exported_name_refuses_a_helper_answer() -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib": ["Mailer"]}
    answer = role(comps, module_use.module_line("lib.mail"), role="helper", symbol="Mailer")
    found = picked(comps, answer, flows=(flow("lib:Sender@abc"),))
    assert [row["cause"] for row in found.refused] == ["flow_source"]
    assert "cites lib:Sender. Thus the map shows that lib.mail takes part" in texts(found)[0]


def test_a_flow_that_cites_the_module_that_defines_a_used_name_of_a_facade() -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib": ["Thing"]}
    answer = role(comps, module_use.module_line("lib"), role="helper", symbol="Thing")
    assert set(picked(comps, answer).accepted) == {"lib"}
    found = picked(comps, answer, flows=(flow("core.thing:Thing@abc"),))
    assert "cites core.thing:Thing. Thus the map shows that lib takes part" in texts(found)[0]


def test_a_mixed_answer_must_give_the_cited_name_in_handoff() -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib.mail": ["Mailer", "Other"]}
    line = module_use.module_line("lib.mail")
    answer = role(comps, line, role="mixed", handoff=("Other",))
    found = picked(comps, answer, flows=(flow("lib.mail:Mailer@abc"),))
    assert texts(found) == [
        f"'{line}': the flow L -> C (a message) cites lib.mail:Mailer, and Mailer is not in "
        'handoff. Add Mailer to handoff, or change the module role to "handoff".'
    ]
    ok = role(comps, line, role="mixed", handoff=("Mailer",))
    assert set(picked(comps, ok, flows=(flow("lib.mail:Mailer@abc"),)).accepted) == {"lib.mail"}


# ---- 7. crossing states ------------------------------------------------------------------

CROSSING = "crossing import: A imports L and no flow connects them"


def states_of(comps: dict[str, Any], **roles: Answer) -> dict[str, str]:
    found = module_use.index(one_map(model(CARDS)), {"components": comps})
    return module_use.crossing_states(found, roles)


def test_the_states_of_an_import_crossing() -> None:
    comps = base_components()
    comps["app.a"]["uses"] = {"lib.h": ["escape"], "lib.mail": ["Mailer"]}
    helper = Answer((LINE_H,), "r", role="helper", symbol="escape")
    assert states_of(comps)[CROSSING] == module_use.WAITING
    assert states_of(comps, **{"lib.h": helper})[CROSSING] == module_use.WAITING
    closed = Answer(("x",), "r", role="mixed", handoff=("Other",))
    assert states_of(comps, **{"lib.h": helper, "lib.mail": closed})[CROSSING] == module_use.CLOSED
    used = Answer(("x",), "r", role="mixed", handoff=("Mailer",))
    assert states_of(comps, **{"lib.mail": used})[CROSSING] == module_use.OPEN
    handoff = Answer(("x",), "r", role="handoff")
    assert states_of(comps, **{"lib.mail": handoff})[CROSSING] == module_use.OPEN
    whole = base_components()
    whole["app.a"]["uses"] = {"lib.h": ["*"]}
    star = Answer(("x",), "r", role="mixed", handoff=("quote",))
    assert states_of(whole, **{"lib.h": star})[CROSSING] == module_use.OPEN
    assert states_of(whole, **{"lib.h": helper})[CROSSING] == module_use.CLOSED


def random_case(rng: random.Random) -> tuple[nest.Tree, dict[str, Any], dict[str, Answer]]:
    modules = [f"m{n}" for n in range(8)]
    cards: dict[str, list[str]] = {"A": [], "B": [], "C": []}
    for module in modules:
        cards[rng.choice("ABC")].append(module)
    comps: dict[str, Any] = {}
    for module in modules:
        uses = {
            t: rng.sample(["n0", "n1", "n2", "*"], rng.randint(1, 2))
            for t in rng.sample(modules, rng.randint(0, 3))
            if t != module
        }
        comps[module] = record(f"{module}.py", uses, tuple(rng.sample(["n0", "n1", "n2", "n3"], 2)))
    tree = one_map(model({c: tuple(m) for c, m in cards.items()}))
    found = module_use.index(tree, {"components": comps})
    accepted: dict[str, Answer] = {}
    for unit in found.units:
        pick = rng.choice(["none", "helper", "handoff", "mixed"])
        if pick != "none":
            accepted[unit] = Answer(
                ("x",), "r", role=pick, handoff=("n1",) if pick == "mixed" else ()
            )
    return tree, {"components": comps}, accepted


def test_the_invariant_of_the_waiting_state_in_random_cases() -> None:
    rng = random.Random(20261121)
    waiting = 0
    for _case in range(200):
        tree, facts, accepted = random_case(rng)
        found = module_use.index(tree, facts)
        present = set(module_use.lines(found, tree))
        for line, state in module_use.crossing_states(found, accepted).items():
            if state != module_use.WAITING:
                continue
            waiting += 1
            missing = [u for u in found.crossings[line].units if u not in accepted]
            assert missing and all(found.units[u].line in present for u in missing)
    assert waiting > 0


def test_the_fallback_opens_a_waiting_crossing_with_no_line() -> None:
    comps = base_components()
    tree = one_map(model(CARDS))
    found = module_use.index(tree, {"components": comps})
    states = module_use.crossing_states(found, {})
    assert states[CROSSING] == module_use.WAITING

    def no_lines(_found: module_use.Index, _tree: nest.Tree) -> list[str]:
        return []

    full = module_use.checked_states(states, found, tree, {}, no_lines)
    assert full[CROSSING] == module_use.OPEN
    scoped = dataclasses.replace(tree, selected="")
    assert (
        module_use.checked_states(states, found, scoped, {}, no_lines)[CROSSING]
        == module_use.WAITING
    )
    assert module_use.checked_states(states, found, tree, {})[CROSSING] == module_use.WAITING


# ---- 8. the pipeline ---------------------------------------------------------------------

READER = "crossing import: Extra imports Reader and no flow connects them"
WRITER = "crossing import: Extra imports Writer and no flow connects them"
USE_READER = module_use.module_line("pkg.reader")
USE_WRITER = module_use.module_line("pkg.writer")


@pytest.fixture
def three(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """The two-card starter with a third card Extra that imports the modules of both."""
    from systemap.cli import main

    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
            "pkg/extra.py": "from pkg.reader import read\nfrom pkg.writer import write\n\n\n"
            "def extra() -> None:\n    read(write(''))\n",
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    path = tmp_path / "map/model.py"
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace(
            "COMPONENTS = (\n",
            'COMPONENTS = (\n    Component(id="Extra", region="core", does="Extra.", '
            'implemented_by=("pkg.extra",), entry="extra", x=80, y=200),\n',
        )
        .replace(
            '"Reader": "the part that reads",',
            '"Reader": "the part that reads", "Extra": "the extra",',
        ),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    return tmp_path


def judged(root: Path, *answers: Answer) -> judgement_json.Judged:
    cfg = config.load(root)
    cfg = dataclasses.replace(cfg, judgement_answered=tuple(answers))
    return judgement_json.evaluate(
        nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root), cfg
    )


def exact(found: judgement_json.Judged, line: str, **keys: Any) -> Answer:
    return Answer((line,), "a test", evidence=found.evidence[line], **keys)


def test_evaluate_hides_the_waiting_and_the_closed_crossing_lines(three: Path) -> None:
    first = judged(three)
    assert READER not in first.lines and WRITER not in first.lines
    assert {READER, WRITER} <= set(first.hidden)
    assert USE_READER in first.lines and USE_WRITER in first.lines
    assert first.crossings[READER]["state"] == module_use.WAITING and first.blocking
    assert first.counts[USE_READER] == (1, "component")
    reader = exact(first, USE_READER, role="handoff")
    writer = exact(first, USE_WRITER, role="helper", symbol="write")
    old = exact(first, WRITER)
    later = judged(three, reader, writer, old, exact(first, READER))
    assert READER in later.lines and READER not in later.result.open
    assert WRITER not in later.lines
    assert later.crossings[WRITER]["state"] == module_use.CLOSED
    # The exact answer for the closed line is not stale: it is an unused answer.
    assert WRITER not in later.result.stale and later.unused == [WRITER]
    assert later.result.unused == [
        f"'{WRITER}' is not necessary: module roles close this import crossing. Remove it "
        "from [judgement] answered."
    ]
    assert "  unused answer: " + later.result.unused[0] in judgement.report(later.result)
    assert not any(line.startswith(("crossing import", "module use")) for line in later.result.open)
    assert later.blocking == bool(later.result.open)
    cfg = config.load(three)
    detail = later.import_rows(nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root))
    assert detail[READER][0] == "handoff modules: pkg.reader"


def test_a_waiting_answer_is_not_stale_and_a_refused_answer_blocks(three: Path) -> None:
    first = judged(three)
    waiting = judged(three, exact(first, READER))
    assert waiting.result.stale == [] and waiting.unused == []
    refused = judged(three, exact(first, USE_READER, role="helper", symbol="nope"))
    assert refused.result.refused and refused.refused_rows[0]["cause"] == "symbol"
    assert USE_READER in refused.result.open and refused.blocking
    rows = judgement_json.role_fields(refused)
    assert rows["module_roles"] == {"helper": 0, "handoff": 0, "mixed": 0, "refused": 1, "none": 1}
    assert rows["import_crossings"]["waiting"] == 2
    # In an import crossing, a module with a refused answer has no module role.
    roles = {
        unit["module"]: unit["role"]
        for crossing in rows["import_crossings"]["crossings"]
        for unit in crossing["modules"]
    }
    assert roles == {"pkg.reader": "none", "pkg.writer": "none"}


def test_the_report_gives_the_count_rows_of_the_import_crossings_and_the_module_roles(
    three: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from systemap.cli import main

    main(["--root", str(three), "judgement", "--brief"])
    out = capsys.readouterr().out.splitlines()
    assert (
        "import crossings: 2 have no flow. 0 are open. 2 wait for module roles. 0 are closed "
        "by module roles."
    ) in out
    assert (
        "module roles: 2 modules. 0 helper, 0 handoff, 0 mixed, 0 refused, 2 with no module role."
    ) in out


def test_a_run_with_map_accepts_the_same_answers() -> None:
    tree, facts = nested_tree()
    scoped, _facts = nested_tree(selected="L", sibling=False)
    found = module_use.index(tree, facts)
    inner = module_use.index(scoped, facts)
    # The import crossing of the map L waits in both runs: the states agree.
    line = "L: crossing import: L2 imports L1 and no flow connects them"
    assert (
        module_use.crossing_states(found, {})[line] == module_use.crossing_states(inner, {})[line]
    )
    answer = Answer(
        ("L: " + LINE_H,),
        "r",
        evidence=module_use.evidence(found)["lib.h"],
        role="handoff",
    )
    full = module_use.roles([answer], found, module_use.evidence(found), tree, facts)
    part = module_use.roles([answer], inner, module_use.evidence(inner), scoped, facts)
    assert set(full.accepted) == set(part.accepted) == {"lib.h"}
    assert (
        module_use.crossing_states(found, full.accepted)[line]
        == module_use.crossing_states(inner, part.accepted)[line]
        == module_use.OPEN
    )


def test_strict_blocks_a_waiting_crossing_in_a_scoped_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", "map/l.py": "# L\n", "map/s.py": "# S\n"})
    init_two_cards(tmp_path, "--no-ci")
    monkeypatch.chdir(tmp_path)
    cfg = dataclasses.replace(config.load(tmp_path), judgement_answered=())
    scoped, facts = nested_tree(selected="L", sibling=False)
    result = cli_scope.judged(judgement_json.evaluate(scoped, facts, cfg), scoped, cfg)
    line = "L: crossing import: L2 imports L1 and no flow connects them"
    assert set(result.crossings) == {line}
    assert result.crossings[line]["state"] == module_use.WAITING
    # With no open line and no refused answer, the waiting import crossing blocks.
    quiet = dataclasses.replace(result, result=judgement.Answered([], 0, []))
    assert quiet.blocking
    # The top map waits too, but the run with --map L does not report it.
    assert "crossing import: A imports L and no flow connects them" not in result.crossings
    evidence = module_use.evidence(module_use.index(scoped, facts))["lib.h"]
    answer = Answer(("L: " + LINE_H,), "r", evidence=evidence, role="helper", symbol="quote")
    cfg = dataclasses.replace(cfg, judgement_answered=(answer,))
    done = cli_scope.judged(judgement_json.evaluate(scoped, facts, cfg), scoped, cfg)
    assert done.crossings[line]["state"] == module_use.CLOSED
    assert not dataclasses.replace(done, result=judgement.Answered([], 0, [])).blocking
    full, _facts = nested_tree()
    whole = judgement_json.evaluate(full, facts, cfg)
    assert whole.crossings[line]["state"] == module_use.CLOSED
