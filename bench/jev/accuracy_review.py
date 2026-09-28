"""Reproduce Jev-free accuracy gaps without running an agent or a service.

Acceptance, stated before execution: all deterministic controls must pass;
each challenge must preserve the stated information or explicitly report
that it cannot. The target is 100% of these contracts. These are deliberately
chosen counterexamples, not a representative dataset or an accuracy rate.
No production code is changed. All source and git fixtures are temporary.

Run: uv run python bench/jev/accuracy_review.py
The JSON records expected behavior, actual behavior and source fingerprints.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from systemap import (
    agent,
    change,
    check,
    delta,
    evidence,
    extract,
    history,
    journeys,
    judgement,
    moves,
    nest,
    trend,
    ways_in,
)
from systemap.config import Answer, Config
from systemap.jev import Cache
from systemap.model import Component, Flow, Journey, Meaning, Model, Step, meaning_problems

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
ROWS: list[dict[str, Any]] = []


def record(case: str, expected: str, met: bool, actual: Any, control: bool = False) -> None:
    ROWS.append(dict(case=case, expected=expected, met=met, actual=actual, control=control))


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def cfg_at(root: Path) -> Config:
    return Config(root=root, name="Review fixture", package_roots=(("pkg", "pkg"),))


def model_of(*cards: Component, flows: tuple[Flow, ...] = ()) -> Model:
    return Model((1000, 1000), (), (), cards, flows, ())


def card(cid: str, module: str, **kwargs: Any) -> Component:
    return Component(cid, "Reads a value.", implemented_by=(module,), entry="run", **kwargs)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(root: Path) -> str:
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Review",
        "-c",
        "user.email=review@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    return git(root, "rev-parse", "HEAD")


def surface_cases() -> None:
    pairs = {
        "function_signature": ("def run(x): pass", "def run(x, y): pass", True),
        "constructor_signature": (
            "class Item:\n def __init__(self, x): pass",
            "class Item:\n def __init__(self, x, y): pass",
            False,
        ),
        "dataclass_field_type": (
            "from dataclasses import dataclass\n@dataclass\nclass Item:\n value: int",
            "from dataclasses import dataclass\n@dataclass\nclass Item:\n value: str",
            False,
        ),
        "public_object_removed": ("app = object()", "", False),
        "reexport_removed": ("from .core import run", "", False),
    }
    for name, (before, after, control) in pairs.items():
        got = change.surface_delta(before, after)
        found = bool(got and any(v for group in got.values() for v in group.values()))
        record(name, "Surface change is recorded.", found, got, control)
    source = "if True:\n def run(): return 1\n"
    surface = extract.parse_surface(source)
    names = [n["name"] for n in (surface or {}).get("names", [])]
    record(
        "conditional_export",
        "The public function run is recorded or marked unresolved.",
        "run" in names,
        names,
    )


def extraction_cases(root: Path) -> None:
    cfg = cfg_at(root)
    write(
        root,
        {"pkg/__init__.py": "", "pkg/good.py": "def run(): return 1", "pkg/bad.py": "def broken(:"},
    )
    facts = extract.build(cfg)
    record(
        "parse_failure_inventory",
        "The invalid source is retained as unknown or extraction fails explicitly.",
        "pkg.bad" in facts["components"] or bool(facts.get("errors")),
        sorted(facts["components"]),
    )
    write(root, {"pkg/__init__.py": "def _register(): pass\n_register()\n"})
    side_effects = extract.build(cfg)["components"]["pkg"]
    record(
        "executable_package_marker",
        "A package executing registration is not an empty marker.",
        not extract.is_empty_marker(side_effects),
        {"empty_marker": extract.is_empty_marker(side_effects)},
    )
    write(
        root,
        {"tests/test_good.py": "from pkg.good import run\ndef test_old(): assert run() == 1\n"},
    )
    before = extract.build(cfg)
    write(
        root,
        {"tests/test_good.py": "from pkg.good import run\ndef test_new(): assert run() == 1\n"},
    )
    after = extract.build(cfg)
    got = extract.drift(after, before)
    record(
        "test_identity_freshness",
        "Replacing a test with another named test makes stored facts stale.",
        bool(got),
        {
            "drift": got,
            "before": before["components"]["pkg.good"]["tests"],
            "after": after["components"]["pkg.good"]["tests"],
        },
    )
    write(root, {"pyproject.toml": '[project.scripts]\ncli = "pkg.good:run"\n'})
    before = extract.build(cfg)
    write(root, {"pyproject.toml": '[project.scripts]\ncli = "pkg.good:other"\n'})
    after = extract.build(cfg)
    got = extract.drift(after, before)
    record(
        "script_target_freshness",
        "Retargeting a console script makes stored facts stale.",
        bool(got),
        {"drift": got, "before": before["entry_points"], "after": after["entry_points"]},
    )
    write(
        root,
        {
            "tests/test_good.py": "from pkg.good import run\nclass TestOne:\n def test_value(self): assert run() == 1\nclass TestTwo:\n def test_value(self): assert run() == 1\n"
        },
    )
    count = extract.build(cfg)["components"]["pkg.good"]["tests_total"]
    record(
        "qualified_test_identity",
        "Two test methods with the same short name are counted separately.",
        count == 2,
        {"tests_total": count},
    )


def evidence_cases() -> None:
    model = model_of(
        card("A", "pkg.a"), card("B", "pkg.b"), flows=(Flow("A", "B", "queue message", "data"),)
    )
    meaning = Meaning(
        plain={"A": "A", "B": "B"}, relations={("A", "B"): "A sends a queue message to B."}
    )
    got = evidence.of_model(model, meaning, {}, ["queue"])[("A", "B")]
    record(
        "prose_as_observation",
        "A mechanism mentioned in prose without source evidence is not observed.",
        got.state != evidence.OBSERVED,
        got.says,
    )
    facts = {"components": {"pkg.a": {"uses": {"pkg.b": ["run"]}}, "pkg.b": {"uses": {}}}}
    got = evidence.of_model(model, meaning, facts)[("A", "B")]
    record(
        "import_evidence_control",
        "A real import is reported as import evidence.",
        got.state == evidence.STRUCTURAL and got.import_present,
        got.says,
        True,
    )
    surface = extract.parse_surface("class Item: pass\ndef run(): pass") or {}
    got = check.interface_problem(
        Component("A", "A", implemented_by=("pkg.a",), interface="Item.run()"), {"pkg.a": surface}
    )
    record(
        "unrelated_method_name",
        "Item.run is rejected when run is only a module function.",
        bool(got),
        got,
    )


def binding_cases() -> None:
    got = extract.internal_uses(
        "from ns.pkg.b import run", {"ns.pkg"}, {"ns.pkg.a", "ns.pkg.b"}, "ns.pkg.a"
    )
    record(
        "dotted_package_root",
        "An import inside a configured dotted package root remains internal.",
        "ns.pkg.b" in got,
        got,
    )
    got = ways_in.in_source("pkg.cli", "from click import command\n@command()\ndef serve(): pass")
    record(
        "imported_command_decorator",
        "A directly imported Click command decorator is recognized.",
        bool(got),
        got,
    )
    raw = "class Cache:\n def get(self, key):\n  return lambda f: f\ncache = Cache()\n@cache.get('/key')\ndef helper(): pass"
    got = ways_in.in_source("pkg.cache", raw)
    record(
        "unrelated_route_decorator",
        "A local cache decorator is not asserted to be an HTTP route.",
        not got,
        got,
    )
    model = model_of(card("A", "pkg.a"), card("B", "pkg.b"))
    before = {"components": {"pkg.a": {"uses": {"pkg.b": ["Type"]}}, "pkg.b": {"uses": {}}}}
    after = {"components": {"pkg.a": {"uses": {"pkg.b": ["send"]}}, "pkg.b": {"uses": {}}}}
    old_line = judgement.crossing_imports_without_flow(model, before)[0]
    new_lines = judgement.crossing_imports_without_flow(model, after)
    got = judgement.apply_answers(
        new_lines,
        [Answer((old_line,), "Only an annotation type is imported.", evidence="old")],
        {old_line: "new"},
    )
    record(
        "answer_dependency_freshness",
        "Replacing a type import with a behavioral import asks for renewed review.",
        bool(got.open),
        {"old_line": old_line, "new_lines": new_lines, "still_answered": got.answered},
    )


def nested_journey_case(root: Path) -> None:
    top = model_of(card("Parent", "pkg.*", map="child.py"))
    sub = model_of(card("Child", "pkg.a"))
    point = dict(kind="route", name="GET /a", module="pkg.a", target="run")
    meaning = Meaning(
        plain={},
        journeys=(
            Journey(
                "walk",
                "Fetch a value",
                (Step(("Parent",), (), ("Parent", "Parent"), "Read."),),
                starts="GET /a",
                covers=(extract.entry_identity(point),),
            ),
        ),
    )
    tree = nest.Tree(
        (
            nest.Map("", root / "model.py", "model.py", top, meaning, {}),
            nest.Map(
                "Parent", root / "child.py", "child.py", sub, Meaning(plain={}), {}, "", "Parent"
            ),
        )
    )
    facts = {
        "components": {"pkg.a": {"names": [{"name": "run"}], "uses": {}, "file": "pkg/a.py"}},
        "entry_points": [point],
    }
    lines = [line for line in judgement.run_tree(tree, facts) if "has no journey" in line]
    record(
        "nested_explicit_start",
        "An explicit journey start on the parent covers the child entry as documented.",
        not lines,
        lines,
    )


def nested_move_case(root: Path) -> None:
    top = model_of(card("Parent", "pkg.old", map="child.py"))
    child = model_of(card("Child", "pkg.old"))
    meaning = Meaning(plain={})
    tree = nest.Tree(
        (
            nest.Map("", root / "model.py", "model.py", top, meaning, {}),
            nest.Map("Parent", root / "child.py", "child.py", child, meaning, {}, "", "Parent"),
        )
    )
    old = {"file": "pkg/old.py", "sha": "identical", "names": [{"name": "run"}], "uses": {}}
    new = dict(old, file="pkg/new.py")
    result = delta.compute_tree(
        cfg_at(root), tree, {"components": {"pkg.old": old}}, {"components": {"pkg.new": new}}
    )
    lines = [line.text for line in result.lines]
    found = [line for line in result.lines if line.text.startswith("Parent:")]
    record(
        "nested_pending_move",
        "An exact move is reported as a move inside a parent whose claim still names the old module.",
        len(found) == 1 and found[0].kind == "moved",
        lines,
    )


def journey_cases(root: Path) -> None:
    point = dict(kind="route", name="GET /read", module="pkg.a", target="run")
    group = journeys.Group((point,), "A")
    model = model_of(
        card("A", "pkg.a"), card("B", "pkg.b"), flows=(Flow("A", "B", "value", "data"),)
    )
    step = dict(edge=["A", "B"], acts=["A"], measures=[], say='A sends the "value" to B.')
    answer = dict(id="walk", label="Read a value", steps=[step])
    draft = journeys.read_answer(json.dumps(answer), model, group)
    assert draft.journey is not None
    source = journeys.add_to_source("JOURNEYS = (\n)\n", draft.journey)
    try:
        ast.parse(source or "")
        parses = True
    except SyntaxError:
        parses = False
    record(
        "journey_string_roundtrip",
        "Ordinary quotation marks produce valid Python source.",
        parses,
        source,
    )
    bad = dict(step, edge=["B", "A"])
    draft = journeys.read_answer(json.dumps(dict(answer, steps=[step, bad])), model, group)
    record(
        "partial_journey_rejection",
        "A journey with an invalid step is refused as a whole.",
        draft.journey is None,
        {
            "kept_steps": len(draft.journey.steps) if draft.journey else 0,
            "problems": draft.problems,
        },
    )
    route2 = dict(point, module="pkg.b")
    facts = {
        "entry_points": [point, route2],
        "components": {"pkg.a": {"file": "pkg/a.py", "sha": "old"}, "pkg.b": {"file": "pkg/b.py"}},
    }
    meaning = Meaning(
        plain={},
        journeys=(
            Journey(
                "walk",
                "Fetch",
                (Step(("A",), (), ("A", "B"), "A reads."),),
                starts="GET /read",
                covers=(extract.entry_identity(point),),
            ),
        ),
    )
    got = journeys.uncovered(meaning, facts)
    record(
        "entry_identity_collision",
        "A journey for one module's route does not cover another module's same-named route.",
        len(got) == 1,
        got,
    )
    main = dict(kind="main_function", name="main", module="pkg.a", target="main")
    got = journeys.uncovered(
        Meaning(plain={}, journeys=(Journey("walk", "The main workflow", ()),)),
        {"entry_points": [main]},
    )
    record(
        "incidental_word_coverage",
        "The word main in prose does not establish coverage of main().",
        len(got) == 1,
        got,
    )
    task = dict(kind="task", name="cleanup", module="pkg.a", target="cleanup")
    crowd = Meaning(plain={}, journeys=(Journey("walk", "HTTP routes", (), starts="A"),))
    got = journeys.uncovered(crowd, {"entry_points": [point, task]}, {"pkg.a": "A"})
    record(
        "crowd_kind_scope",
        "A grouped HTTP journey does not also cover a background task.",
        task in got,
        got,
    )
    blank = Meaning(
        plain={"A": "A", "B": "B"},
        relations={("A", "B"): "A sends to B."},
        journeys=(Journey("empty", "Empty", (), starts="A"),),
    )
    got = meaning_problems(model, blank) + judgement.journey_problems(blank, facts, model.ids)
    record(
        "empty_journey_validation",
        "A zero-step journey is rejected or asked for review.",
        bool(got),
        got,
    )
    calls: list[str] = []

    def transport(_command: str, _question: str, cwd: Path, _timeout: float) -> str:
        calls.append((cwd / "pkg/a.py").read_text())
        return json.dumps(answer)

    writer = agent.Agent("injected", root, Cache(root / "cache.json"), run_command=transport)
    write(root, {"pkg/a.py": "def run(): return 'old'", "pkg/b.py": "def run(): pass"})
    journeys.write_one(writer, model, Meaning(plain={}), facts, group)
    write(root, {"pkg/a.py": "def run(): return 'new'"})
    facts["components"]["pkg.a"]["sha"] = "new"
    journeys.write_one(writer, model, Meaning(plain={}), facts, group)
    record(
        "journey_cache_source_freshness",
        "A source change invalidates the code-reading agent answer.",
        len(calls) == 2,
        {"calls": len(calls), "cached": writer.usage.cached},
    )


def diff_cases(root: Path) -> None:
    git(root, "init", "-q")
    cfg = cfg_at(root)
    write(
        root,
        {
            "pkg/__init__.py": "",
            "pkg/a.py": "def run(): return 'allow'\n",
            "pkg/b.py": "def run(): return 1\n",
        },
    )
    base = commit(root)
    before = extract.build(cfg)
    model = model_of(card("A", "pkg.a"), card("B", "pkg.b"))
    write(root, {"pkg/a.py": "def run(): return 'deny'\n", "pkg/b.py": "def run(): return 2\n"})
    head = commit(root)
    after = extract.build(cfg)
    got = delta.compute(cfg, model, Meaning(plain={}), before, after)
    record(
        "body_change_review",
        "Behavior changes in every card request semantic review, including the full-loop trigger.",
        bool(got.open) and got.past_a_third,
        {
            "changed": got.changed,
            "open": len(got.open),
            "named": got.named,
            "past_a_third": got.past_a_third,
            "report": delta.report(got, teach=False),
        },
    )
    got_change = change.compute(cfg, model, base, after, head)
    record(
        "body_change_overlay_control",
        "The change overlay highlights cards with body-only changes.",
        got_change["direct"] == {"A", "B"},
        sorted(got_change["direct"]),
        True,
    )
    try:
        got_change = change.compute(cfg, model, "nonexistent-ref", after, head)
        failed = False
        detail: Any = {"has_change": got_change["has_change"]}
    except Exception as exc:
        failed, detail = True, str(exc)
    record(
        "invalid_ref_refusal", "A missing comparison ref raises an explicit error.", failed, detail
    )
    first = history.facts_at(cfg, head)
    renamed_cfg = dataclasses.replace(cfg, package_roots=(("pkg", "other"),))
    second = history.facts_at(renamed_cfg, head)
    fresh = delta.facts_at(renamed_cfg, head)
    record(
        "history_cache_configuration",
        "History cache incorporates extraction configuration.",
        second["components"].keys() == fresh["components"].keys(),
        {
            "cached": sorted(second["components"]),
            "fresh": sorted(fresh["components"]),
            "first": sorted(first["components"]),
        },
    )
    write(root, {"pkg/a.py": "def broken(:\n"})
    invalid_head = commit(root)
    try:
        got_change = change.compute(cfg, model, head, extract.build(cfg), invalid_head)
        detail = {"unparsed": got_change["unparsed"]}
        safe = got_change["unparsed"] == ["pkg.a"]
    except Exception as exc:
        safe, detail = False, f"{type(exc).__name__}: {exc}"
    record(
        "unparsed_change_report",
        "An owned file that cannot parse is reported as unknown without crashing.",
        safe,
        detail,
    )


def snapshot_cases(root: Path) -> None:
    git(root, "init", "-q")
    cfg = cfg_at(root)
    write(
        root,
        {
            "pkg/__init__.py": "",
            "pkg/a.py": "def run(): return 1\n",
            "pkg/b.py": "from pkg.a import run\n",
        },
    )
    base = commit(root)
    write(root, {"pkg/a.py": "def run(): return 2\n"})
    head = commit(root)
    target_facts = extract.build(cfg)
    write(root, {"pkg/b.py": "def independent(): return 3\n"})
    commit(root)
    working_facts = extract.build(cfg)
    model = model_of(card("A", "pkg.a"), card("B", "pkg.b"))
    got = change.compute(cfg, model, base, working_facts, head)
    correct = change.compute(cfg, model, base, target_facts, head)
    record(
        "explicit_head_graph",
        "Reach for an explicit head uses that head's import graph.",
        got["adjacent"] == correct["adjacent"],
        {
            "working_facts_adjacent": sorted(got["adjacent"]),
            "target_facts_adjacent": sorted(correct["adjacent"]),
        },
    )
    symbol_model = model_of(card("A", "pkg.a"), card("Symbol", "pkg.a:run"))
    got = change.compute(cfg, symbol_model, base, target_facts, head)
    record(
        "symbol_claim_change_overlay",
        "A body change to a claimed symbol highlights its symbol card.",
        "Symbol" in got["direct"],
        sorted(got["direct"]),
    )
    old_cfg = cfg
    renamed_model = model_of(card("A", "pkg.c"))
    before = trend.sample_at(old_cfg, renamed_model, head)
    git(root, "mv", "pkg/a.py", "pkg/c.py")
    renamed = commit(root)
    after = trend.sample_at(old_cfg, renamed_model, renamed)
    got = trend.between(before, after)
    record(
        "trend_rename_caveat",
        "A current-name-only card count does not present a pure file rename as real growth without qualification.",
        not got.grew,
        {"grew": got.grew, "modules": got.modules},
    )


def move_cases() -> None:
    old = {
        "pkg.email": {
            "file": "pkg/email.py",
            "sha": "email",
            "names": [{"name": "run", "kind": "function"}],
        }
    }
    new = {
        "pkg.billing": {
            "file": "pkg/billing.py",
            "sha": "billing",
            "names": [{"name": "run", "kind": "function"}],
        }
    }
    found = moves.find(old, new, list(old), list(new))
    record(
        "unrelated_same_name_move",
        "Identical common names alone do not assert an unrelated delete/add is a move.",
        not found,
        found,
    )
    new["pkg.billing"]["sha"] = "email"
    found = moves.find(old, new, list(old), list(new))
    record(
        "exact_content_move_control",
        "A unique exact-content move is recognized.",
        bool(found),
        found,
        True,
    )


def main() -> None:
    surface_cases()
    evidence_cases()
    binding_cases()
    move_cases()
    with tempfile.TemporaryDirectory(prefix="systemap-accuracy-") as tmp:
        for name, fn in (
            ("extraction", extraction_cases),
            ("journey", journey_cases),
            ("diff", diff_cases),
            ("snapshot", snapshot_cases),
            ("nested", nested_journey_case),
            ("nested_move", nested_move_case),
        ):
            root = Path(tmp) / name
            root.mkdir()
            fn(root)
    result = {
        "revision": git(ROOT, "rev-parse", "HEAD"),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "src/systemap").glob("*.py"))
        },
        "cases": ROWS,
        "note": "Targeted counterexamples and controls. These counts are not an accuracy estimate.",
    }
    path = HERE / "results/no-jev-accuracy-review.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    for row in ROWS:
        print(f"{'PASS' if row['met'] else 'GAP ':4} {row['case']}: {json.dumps(row['actual'])}")
    print(f"{sum(r['met'] for r in ROWS)}/{len(ROWS)} contracts met; {path}")


if __name__ == "__main__":
    main()
