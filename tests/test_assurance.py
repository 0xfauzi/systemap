"""The assurance level of each claim: `established`, `examined`, or `unknown`.

Acceptance values, for a Python fixture and a TypeScript fixture with the same three
components (Api, Core, Store), one flow Api -> Core, invariants, and import rules:

1. An import rule with the result `pass` is `established`. A rule with the result `fail`
   or `unknown` is `unknown`.
2. A component with a current source review is `examined` and `current`. After a source
   change, it is `unknown` and `stale`. Without a review, it is `unknown` and `missing`.
3. A flow with a current flow review that cites a module of an endpoint is `examined` and
   `current`. After a change to the cited source, it is `unknown` and `stale`. Without a
   review, it is `unknown`, also when an import connects the two components.
4. An invariant is `examined` when each applicable component has a current source review.
   A linked import rule with the result `pass` does not make it `established`. A linked
   rule with the result `fail` makes it `unknown`.
5. No claim type other than an import rule gets `established`. A stale review never
   gives `examined` with `current`. An actor has no level.
6. An `unknown` level is never a pass: under `[rules] unknown = "warn"` the rule check
   passes, and the level stays `unknown`. The counts have no key for a pass.
7. `judgement --json` gives schema version 7 with one `assurance` row for each claim.
8. The page gives the level and the freshness of each component, flow, invariant, and
   import rule. No level text says "verified" or "proven".
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample, init_two_cards, page_detail, write_tree
from test_import_rules import LANGUAGES, _facts

from systemap import (
    assurance,
    card_review,
    config,
    facts_file,
    flow_review,
    import_rules,
    judgement_json,
    nest,
    page,
)
from systemap.assurance import ESTABLISHED, EXAMINED, UNKNOWN
from systemap.cli import main
from systemap.model import Component, Flow, ImportRule, Invariant, Meaning, Model

MEANING = Meaning(plain={})
# A change to the syntax of the Api module in each language.
CHANGED_API = {
    "python": {
        "pkg/api.py": (
            "import requests\n\nfrom pkg.core import run\n\n\ndef serve():\n    return run()\n"
            "\n\ndef extra():\n    return 2\n"
        )
    },
    "typescript": {
        "src/api.ts": (
            'import { z } from "zod";\nimport { run } from "./core";\n'
            "export function serve(): unknown {\n  return [z, run()];\n}\n"
            "export function extra(): number {\n  return 2;\n}\n"
        )
    },
}


@pytest.fixture(params=sorted(LANGUAGES))
def language(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def _cards(prefix: str) -> tuple[Component, ...]:
    return tuple(
        Component(name.title(), f"The {name} part.", implemented_by=(f"{prefix}.{name}",))
        for name in ("api", "core", "store")
    )


def _model(
    prefix: str,
    flows: tuple[Flow, ...] = (),
    invariants: tuple[Invariant, ...] = (),
    rules: tuple[ImportRule, ...] = (),
) -> Model:
    return Model((800, 600), (), (), _cards(prefix), flows, (), invariants, rules)


def _ref(facts: dict[str, Any], module: str) -> str:
    return f"{module}@{facts['components'][module]['source_sha256']}"


def _flow(prefix: str, facts: dict[str, Any], cited: str = "api") -> Flow:
    """The flow Api -> Core with one source record and its current review digest."""
    flow = Flow("Api", "Core", "request", "control", (_ref(facts, f"{prefix}.{cited}"),))
    digest = flow_review.digest(flow, MEANING, facts)
    assert digest is not None
    return dataclasses.replace(flow, review_digest=digest)


def _reviewed(model: Model, facts: dict[str, Any], *ids: str) -> Model:
    """Record the current source review digest of each named component."""
    cards = []
    for card in model.components:
        digest = card_review.digest(card, model, MEANING, facts) if card.id in ids else None
        cards.append(dataclasses.replace(card, source_review=digest or card.source_review))
    return dataclasses.replace(model, components=tuple(cards))


def _levels(model: Model, facts: dict[str, Any]) -> dict[tuple[str, str], assurance.Claim]:
    return {(c.type, c.id): c for c in assurance.of_model(model, MEANING, facts)}


def _pair(claim: assurance.Claim) -> tuple[str, str]:
    return claim.level, claim.freshness


# ---- import rules ---------------------------------------------------------------------


def test_an_import_rule_is_established_only_when_it_passes(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    model = _model(
        prefix,
        rules=(
            ImportRule("api-no-store", "forbid_import", ("Api",), ("Store",), "A reason."),
            ImportRule("core-no-store", "forbid_import", ("Core",), ("Store",), "A reason."),
        ),
    )
    found = _levels(model, facts)
    passed, failed = found[("import_rule", "api-no-store")], found[("import_rule", "core-no-store")]
    assert (_pair(passed), passed.basis) == ((ESTABLISHED, "current"), "rule_pass")
    assert (_pair(failed), failed.basis) == ((UNKNOWN, "current"), "rule_fail")


def test_an_unknown_rule_result_is_never_a_pass(tmp_path: Path, language: str) -> None:
    prefix, tree, _cycle, broken, _unresolved = LANGUAGES[language]
    facts = _facts(tmp_path, tree, broken)
    model = _model(
        prefix, rules=(ImportRule("store-alone", "forbid_import", ("Store",), ("Api",)),)
    )
    # The rule check accepts an unknown result under the default policy.
    assert import_rules.ok(import_rules.run_tree(_tree(model), facts), "warn")
    claim = _levels(model, facts)[("import_rule", "store-alone")]
    assert (_pair(claim), claim.basis) == ((UNKNOWN, "current"), "rule_unknown")
    counts = assurance.counts([claim])
    assert counts == {ESTABLISHED: 0, EXAMINED: 0, UNKNOWN: 1}


def test_rules_without_facts_are_unknown_and_missing() -> None:
    model = _model("pkg", rules=(ImportRule("a", "forbid_import", ("Api",), ("Store",)),))
    claim = _levels(model, {})[("import_rule", "a")]
    assert _pair(claim) == (UNKNOWN, "missing")


# ---- components -------------------------------------------------------------------------


def test_component_levels_follow_the_source_review(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    model = _reviewed(_model(prefix), facts, "Api", "Core")
    found = _levels(model, facts)
    assert _pair(found[("component", "Api")]) == (EXAMINED, "current")
    assert _pair(found[("component", "Store")]) == (UNKNOWN, "missing")

    changed = _facts(tmp_path, CHANGED_API[language])
    found = _levels(model, changed)
    # A stale review is not examined and current.
    assert _pair(found[("component", "Api")]) == (UNKNOWN, "stale")
    assert _pair(found[("component", "Core")]) == (EXAMINED, "current")


def test_an_actor_has_no_level(tmp_path: Path) -> None:
    prefix, tree, *_ = LANGUAGES["python"]
    facts = _facts(tmp_path, tree)
    model = _model(prefix)
    user = Component("User", "A person who uses the system.", kind="actor")
    model = dataclasses.replace(model, components=(*model.components, user))
    assert ("component", "User") not in _levels(model, facts)


# ---- flows -------------------------------------------------------------------------------


def test_flow_levels_follow_the_flow_review(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    model = _model(prefix, flows=(_flow(prefix, facts),))
    claim = _levels(model, facts)[("flow", "Api->Core")]
    assert (_pair(claim), claim.basis) == ((EXAMINED, "current"), "flow_review_current")

    changed = _facts(tmp_path, CHANGED_API[language])
    claim = _levels(model, changed)[("flow", "Api->Core")]
    assert (_pair(claim), claim.basis) == ((UNKNOWN, "stale"), "flow_review_stale")


def test_an_import_alone_does_not_establish_a_flow(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    model = _model(prefix, flows=(Flow("Api", "Core", "request", "control"),))
    claim = _levels(model, facts)[("flow", "Api->Core")]
    assert (_pair(claim), claim.basis) == ((UNKNOWN, "missing"), "flow_review_missing")


def test_a_review_that_cites_no_endpoint_is_unknown(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    model = _model(prefix, flows=(_flow(prefix, facts, cited="store"),))
    claim = _levels(model, facts)[("flow", "Api->Core")]
    assert (_pair(claim), claim.basis) == ((UNKNOWN, "current"), "citation_outside_endpoints")


def test_a_review_earlier_than_source_tracking_is_examined(tmp_path: Path) -> None:
    prefix, tree, *_ = LANGUAGES["python"]
    facts = _facts(tmp_path, tree)
    flow = _flow(prefix, facts)
    flow = dataclasses.replace(flow, review_digest=flow_review.earlier_digest(flow, MEANING))
    claim = _levels(_model(prefix, flows=(flow,)), facts)[("flow", "Api->Core")]
    assert (_pair(claim), claim.basis) == ((EXAMINED, "earlier"), "flow_review_earlier")


# ---- invariants --------------------------------------------------------------------------


def _contract() -> tuple[tuple[Invariant, ...], tuple[ImportRule, ...]]:
    invariants = (
        Invariant(1, "Core does not use Api.", ("Core",), "A reason."),
        Invariant(2, "Core does not use Store.", ("Core",), "A reason."),
        Invariant(3, "Each part has one task.", (), "A reason."),
    )
    rules = (
        ImportRule("core-no-api", "forbid_import", ("Core",), ("Api",), "A reason.", 1),
        ImportRule("core-no-store", "forbid_import", ("Core",), ("Store",), "A reason.", 2),
    )
    return invariants, rules


def test_invariant_levels(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    invariants, rules = _contract()
    model = _model(prefix, invariants=invariants, rules=rules)
    found = _levels(model, facts)
    # A linked rule with the result pass does not establish the text of the invariant.
    assert (_pair(found[("invariant", "1")]), found[("invariant", "1")].basis) == (
        (UNKNOWN, "missing"),
        "source_review_missing",
    )

    model = _reviewed(model, facts, "Api", "Core")
    found = _levels(model, facts)
    assert (_pair(found[("invariant", "1")]), found[("invariant", "1")].basis) == (
        (EXAMINED, "current"),
        "source_review_current",
    )
    assert (_pair(found[("invariant", "2")]), found[("invariant", "2")].basis) == (
        (UNKNOWN, "current"),
        "rule_fail",
    )
    # Invariant 3 applies to all components, and Store has no review.
    assert _pair(found[("invariant", "3")]) == (UNKNOWN, "missing")

    model = _reviewed(model, facts, "Store")
    assert _pair(_levels(model, facts)[("invariant", "3")]) == (EXAMINED, "current")
    changed = _facts(tmp_path, CHANGED_API[language])
    assert _pair(_levels(model, changed)[("invariant", "3")]) == (UNKNOWN, "stale")


def test_only_an_import_rule_can_be_established(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    invariants, rules = _contract()
    model = _model(prefix, (_flow(prefix, facts),), invariants, rules)
    model = _reviewed(model, facts, "Api", "Core", "Store")
    claims = assurance.of_model(model, MEANING, facts)
    assert {c.type for c in claims} == set(assurance.TYPES)
    assert {c.type for c in claims if c.level == ESTABLISHED} == {"import_rule"}
    for claim in claims:
        if claim.freshness in ("stale", "missing"):
            assert claim.level == UNKNOWN


# ---- the map tree, the JSON object, and the page -----------------------------------------


def _tree(model: Model) -> nest.Tree:
    return nest.Tree((nest.Map("", Path("map/model.py"), "map/model.py", model, MEANING, {}),))


def test_of_tree_gives_the_map_of_each_claim(tmp_path: Path) -> None:
    prefix, tree, *_ = LANGUAGES["python"]
    facts = _facts(tmp_path, tree)
    claims = assurance.of_tree(_tree(_model(prefix)), facts)
    assert [(c.map, c.type, c.id) for c in claims] == [
        ("", "component", "Api"),
        ("", "component", "Core"),
        ("", "component", "Store"),
    ]
    assert claims[0].row() == {
        "map": "",
        "type": "component",
        "id": "Api",
        "level": UNKNOWN,
        "freshness": "missing",
        "basis": "source_review_missing",
    }


@pytest.fixture(params=["python", "typescript"])
def project(
    request: pytest.FixtureRequest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> Path:
    if request.param == "python":
        write_tree(
            tmp_path,
            {
                "pkg/__init__.py": "",
                "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
                "pkg/writer.py": (
                    "from pkg.reader import read\n\n\n"
                    "def write(request: str) -> str:\n    return read(request)\n"
                ),
            },
        )
        init_two_cards(tmp_path, "--no-ci")
        assert main(["--root", str(tmp_path), "extract"]) == 0
    else:
        fixture = Path(__file__).parent / "fixtures" / "typescript-app"
        shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
        assert main(["--root", str(tmp_path), "refresh"]) == 0
    capsys.readouterr()
    return tmp_path


def test_judgement_json_gives_one_row_for_each_claim(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["--root", str(project), "judgement", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["schema_version"] == 7 == judgement_json.SCHEMA_VERSION
    tree = nest.load(config.load(project))
    cfg = config.load(project)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root) or {}
    expected = [c.row() for c in assurance.of_tree(tree, facts)]
    assert out["assurance"]["claims"] == expected and expected
    sources = [c for m in tree.maps for c in m.model.components if c.kind != "actor"]
    rows = [r for r in expected if r["type"] == "component"]
    assert len(rows) == len(sources)
    assert set(out["assurance"]["counts"]) == {ESTABLISHED, EXAMINED, UNKNOWN}
    assert sum(out["assurance"]["counts"].values()) == len(expected)


def test_an_empty_report_has_an_empty_assurance_object() -> None:
    assert judgement_json.empty()["assurance"] == {
        "counts": {ESTABLISHED: 0, EXAMINED: 0, UNKNOWN: 0},
        "claims": [],
    }


def _detail(html: str) -> dict[str, Any]:
    return page_detail(html)


def test_the_page_gives_the_level_of_each_claim(sample: Sample) -> None:
    model, facts = sample.model, sample.facts
    rule = ImportRule("writer-no-reader", "forbid_import", ("Writer",), ("Reader",), "A reason.", 1)
    flow = Flow("Writer", "Ledger", "record", "record", (_ref(facts, "pkg.writer"),))
    flow = dataclasses.replace(flow, review_digest=flow_review.digest(flow, sample.meaning, facts))
    flows = tuple(flow if f.edge == flow.edge else f for f in model.flows)
    model = dataclasses.replace(model, flows=flows, import_rules=(rule,))
    digest = card_review.digest(model.component("Writer"), model, sample.meaning, facts)
    cards = tuple(
        dataclasses.replace(c, source_review=digest or "") if c.id == "Writer" else c
        for c in model.components
    )
    model = dataclasses.replace(model, components=cards)
    html = page.build(sample.cfg, model, sample.meaning, sample.theme, facts, {})
    detail = _detail(html)
    assert (detail["Writer"]["assurance"]["level"], detail["Writer"]["assurance"]["freshness"]) == (
        EXAMINED,
        "current",
    )
    assert detail["Reader"]["assurance"]["freshness"] == "missing"
    assert "assurance" not in detail["User"]
    edges = {(e["from"], e["to"]): e["assurance"] for e in detail["_meta"]["edges"]}
    assert edges[("Writer", "Ledger")]["level"] == EXAMINED
    assert edges[("Parser", "Writer")]["level"] == UNKNOWN
    # The page has the text of each level and each basis one time.
    text = detail["_meta"]["assurance_text"]
    assert all(text[e["level"]] and text[e["basis"]] for e in edges.values())
    # Invariant 1 applies to Writer only. Invariant 2 applies also to Ledger, with no review.
    levels = {r["n"]: r["assurance"]["level"] for r in detail["_meta"]["rules"]}
    assert levels == {1: EXAMINED, 2: UNKNOWN}
    # The rules panel gives the level of each invariant and each import rule.
    panel = html[html.index('id="invariants"') :]
    panel = panel[: panel.index("</details>")]
    assert panel.count('data-level="') == 3
    assert 'data-level="established"' in panel and "writer-no-reader" in panel


def test_no_level_text_says_verified_or_proven() -> None:
    texts = [*assurance.LEVEL_TEXT.values(), *assurance.BASIS_TEXT.values()]
    assert len(assurance.BASIS_TEXT) == len(assurance.BASES)
    for text in texts:
        assert not re.search(r"verif|prove|proof", text, re.IGNORECASE), text


SCENARIO = r"""
function assurancepanel(page) {
  const {doc, win, A} = page;
  const panel = doc.getElementById('panel');
  const writer = A.edges.findIndex(e => e.from === 'Writer' && e.to === 'Ledger');
  A.inspectFlow(writer, 'Writer'); runFrames(win);
  return panel.querySelectorAll('.systemap-f__assurance').map(el => ({
    level: el.getAttribute('data-level'),
    freshness: el.getAttribute('data-freshness'),
    text: el.textContent,
  }));
}
"""


def test_the_inspector_shows_the_level_text(sample: Sample, tmp_path: Path) -> None:
    """The panel script gives one row for the component, the flow, and each invariant."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("generated navigation JavaScript needs Node")
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = (Path(__file__).with_name("page_driver.js")).read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, assurancepanel};",
    )
    harness = tmp_path / "assurance.js"
    harness.write_text(driver + SCENARIO, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "assurancepanel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    rows: list[dict[str, str]] = json.loads(result.stdout)
    # The Writer component, the Writer -> Ledger flow, and invariants 1 and 2.
    assert len(rows) == 4
    for row in rows:
        assert (row["level"], row["freshness"]) == (UNKNOWN, "missing")
        assert row["text"].startswith("unknown · missing ")
        assert assurance.LEVEL_TEXT[UNKNOWN] in row["text"]
