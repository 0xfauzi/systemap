"""Rule proposals: an import rule that the text of an invariant states, as a judgement line.

Acceptance values:

1. An invariant "Core must not import Store" with `governs=("Core", "Store")` gives the
   proposal `forbid_import` from Core to Store. A Python fixture and a TypeScript fixture.
2. An invariant that already has a linked `ImportRule` gives no proposal.
3. An invariant with no dependency form gives no deterministic proposal.
4. `systemap check` exit codes are identical with and without proposals.
5. Without `--propose-rules`, `systemap judgement` sends zero provider requests. An injected
   transport counts them.
6. All tests that were in the suite before this change pass.

No test calls Jev or OpenAI. The transport is a function in this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_import_rules import PYTHON, TYPESCRIPT

from systemap import config, decision, explain, jev, judgement, nest, rule_proposal, rule_question
from systemap.cli import main
from systemap.decision import ChoiceQuestion
from systemap.model import Component, ImportRule, Invariant, Model

CORE_STORE = "Core must not import Store."


def _model(*invariants: Invariant, rules: tuple[ImportRule, ...] = ()) -> Model:
    cards = tuple(
        Component(name, f"The {name.lower()} part.", implemented_by=(f"pkg.{name.lower()}",))
        for name in ("Api", "Core", "Store")
    )
    user = Component("User", "A person.", kind="actor")
    return Model(
        (800, 600), (), (), (*cards, user), (), (), invariants=invariants, import_rules=rules
    )


def _rules(text: str, governs: tuple[str, ...] = ("Core", "Store")) -> list[ImportRule]:
    return [p.rule for p in rule_proposal.proposals(_model(Invariant(1, text, governs)))]


# ---- the patterns ----------------------------------------------------------------------


def test_core_must_not_import_store_gives_forbid_import() -> None:
    """Acceptance 1 for the model alone."""
    found = rule_proposal.proposals(_model(Invariant(3, CORE_STORE, ("Core", "Store"))))
    assert [p.rule for p in found] == [
        ImportRule("invariant-3", "forbid_import", ("Core",), ("Store",), invariant=3)
    ]
    assert rule_proposal.line(found[0]) == (
        'rule proposal: invariant 3 can be ImportRule("invariant-3", "forbid_import", '
        '("Core",), ("Store",), invariant=3)'
    )


@pytest.mark.parametrize(
    "text",
    [
        "Core does not import Store.",
        "Core never imports Store (pkg/core.py:3).",
        "The Core component must not depend on the Store component.",
        "Core does not depend on Store; it gets the data from Api.",
        "Modules of Core must not call Store.",
        "Core cannot import from Store.",
    ],
)
def test_the_forbid_forms(text: str) -> None:
    assert _rules(text) == [
        ImportRule("invariant-1", "forbid_import", ("Core",), ("Store",), invariant=1)
    ]


def test_a_list_of_components_gives_one_rule_with_the_list() -> None:
    assert _rules("Api and Core must not import Store or User.") == [
        ImportRule("invariant-1", "forbid_import", ("Api", "Core"), ("Store", "User"), invariant=1)
    ]


@pytest.mark.parametrize(
    "text",
    ["Api imports only Core.", "Api depends only on Core.", "Api must only import from Core."],
)
def test_the_allow_forms(text: str) -> None:
    assert _rules(text, ("Api", "Core")) == [
        ImportRule("invariant-1", "allow_imports", ("Api",), ("Core",), invariant=1)
    ]


def test_only_x_calls_y_forbids_the_other_components() -> None:
    """The actor User has no modules. The rule does not name it."""
    assert _rules("Only Core calls Store.") == [
        ImportRule("invariant-1", "forbid_import", ("Api",), ("Store",), invariant=1)
    ]


@pytest.mark.parametrize(
    "text",
    [
        "No import cycle connects Api, Core and Store.",
        "There is no cycle between Api, Core, and Store.",
    ],
)
def test_the_cycle_forms(text: str) -> None:
    assert _rules(text, ()) == [
        ImportRule("invariant-1", "forbid_cycle", ("Api", "Core", "Store"), invariant=1)
    ]


def test_a_linked_rule_stops_the_proposal() -> None:
    """Acceptance 2."""
    linked = ImportRule("core-alone", "forbid_import", ("Core",), ("Api",), invariant=3)
    model = _model(Invariant(3, CORE_STORE, ("Core", "Store")), rules=(linked,))
    assert rule_proposal.proposals(model) == []
    # A rule for a different invariant does not stop it.
    other = ImportRule("other", "forbid_import", ("Api",), ("Store",), invariant=None)
    model = _model(Invariant(3, CORE_STORE, ("Core", "Store")), rules=(other,))
    assert [p.rule.id for p in rule_proposal.proposals(model)] == ["invariant-3"]


@pytest.mark.parametrize(
    "text",
    [
        "Core keeps the records of each request (pkg/core.py:3).",
        "Core must not import Store unless the request is old.",
        "Core must not import the database.",
        "core must not import store.",
        "Nothing in Core reads Store.",
        "Core must not import Core.",
        "Only Core and Api and Store call Store.",
        "No import cycle connects Core.",
    ],
)
def test_no_dependency_form_gives_no_proposal(text: str) -> None:
    """Acceptance 3. The patterns accept only component ids, list words, and fill words."""
    assert _rules(text) == []


def test_a_taken_rule_id_gets_a_number() -> None:
    taken = ImportRule("invariant-1", "forbid_cycle", (), invariant=None)
    model = _model(
        Invariant(1, "Core must not import Store. Api must not import Store."), rules=(taken,)
    )
    assert [p.rule.id for p in rule_proposal.proposals(model)] == ["invariant-1-2", "invariant-1-3"]


def test_the_kind_has_a_lesson_and_answers_accept_it() -> None:
    lesson = explain.lesson("rule proposal")
    assert lesson is not None and lesson.means and lesson.why and lesson.do
    assert "rule proposal" in config.LINE_KINDS
    line = "rule proposal: invariant 1 can be ImportRule(...)"
    assert judgement.kind_of(line) == "rule proposal"
    assert judgement.kind_of("Sub: " + line) == "rule proposal"


def test_no_provider_has_a_measured_value_for_the_rule_question() -> None:
    """The provider step gives information only until a measurement gives a value.

    If a measurement adds a value, add the proposal step for it, and change this test.
    """
    assert all(limits.rule_at is None for limits in decision.THRESHOLDS.values())


# ---- the command, for each language ----------------------------------------------------

PROJECT_MODEL = """from systemap.model import (
    Component, Container, ImportRule, Invariant, Meaning, Model, Region,
)

CONTAINERS = (Container(id="system", label="SYSTEM", box=(20, 20, 900, 300), tone="server"),)
REGIONS = (
    Region(id="application", label="APPLICATION", box=(40, 60, 860, 220), container="system"),
)
COMPONENTS = (
    Component(id="Api", does="Serves the requests.", implemented_by=("{p}.api",),
              entry="serve", region="application"),
    Component(id="Core", does="Runs the work.", implemented_by=("{p}.core",),
              entry="run", region="application"),
    Component(id="Store", does="Keeps the records.", implemented_by=("{p}.store",),
              entry="save", region="application"),
)
INVARIANTS = (
    Invariant(1, "{text}", governs=("Core", "Store")),
    Invariant(2, "Api keeps one record of each request.", governs=("Api",)),
)
MODEL = Model(
    canvas=(940, 340),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=(),
    flow_kinds=(),
    invariants=INVARIANTS,
    import_rules=({rules}),
)
MEANING = Meaning(plain={{"Api": "the API", "Core": "the core", "Store": "the store"}})
"""
LANGUAGES = {"python": ("pkg", PYTHON), "typescript": ("web", TYPESCRIPT)}


def write_model(root: Path, prefix: str, text: str) -> None:
    body = PROJECT_MODEL.format(p=prefix, text=text, rules="")
    (root / "map").mkdir(exist_ok=True)
    (root / "map/model.py").write_text(body, encoding="utf-8")


def edit_model(root: Path, old: str, new: str) -> None:
    """Change the model file and keep the positions that `systemap place` wrote."""
    path = root / "map/model.py"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


@pytest.fixture(params=sorted(LANGUAGES))
def project(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Path, str]:
    prefix, tree = LANGUAGES[request.param]
    write_tree(tmp_path, tree)
    write_model(tmp_path, prefix, CORE_STORE)
    assert main(["--root", str(tmp_path), "extract"]) == 0
    assert main(["--root", str(tmp_path), "place"]) == 0
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    return tmp_path, prefix


def judgement_json(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> Any:
    capsys.readouterr()
    assert main(["--root", str(root), "judgement", "--json", *argv]) == 0
    return json.loads(capsys.readouterr().out)


def test_the_command_gives_the_proposal_for_each_language(
    project: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1 through `systemap judgement`, text and JSON."""
    root, _prefix = project
    obj = judgement_json(root, capsys)
    line = (
        'rule proposal: invariant 1 can be ImportRule("invariant-1", "forbid_import", '
        '("Core",), ("Store",), invariant=1)'
    )
    rows = [row for row in obj["open"] if row["kind"] == "rule proposal"]
    assert [row["line"] for row in rows] == [line]
    assert rows[0]["evidence"]
    assert obj["rule_proposals"] == [
        {
            "map": "",
            "invariant": 1,
            "line": line,
            "rule": {
                "id": "invariant-1",
                "kind": "forbid_import",
                "src": ["Core"],
                "dst": ["Store"],
                "invariant": 1,
            },
            "text": line.split(" can be ", 1)[1],
            "pattern": "forbid",
            "open": True,
        }
    ]
    assert obj["kinds"]["rule proposal"] == {"open": 1, "answered": 0}
    assert "rule_questions" not in obj
    capsys.readouterr()
    assert main(["--root", str(root), "judgement"]) == 0
    out = capsys.readouterr().out
    assert line in out
    assert explain.rows("rule proposal")[0] in out


def test_an_exact_answer_closes_the_proposal(
    project: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, _prefix = project
    row = next(r for r in judgement_json(root, capsys)["open"] if r["kind"] == "rule proposal")
    answer = (
        f"\n[judgement]\n[[judgement.answered]]\nitem = {json.dumps(row['line'])}\n"
        f'reason = "The core reads the store in a test."\nevidence = "{row["evidence"]}"\n'
    )
    toml = root / "systemap.toml"
    toml.write_text(
        (toml.read_text(encoding="utf-8") if toml.exists() else "") + answer, encoding="utf-8"
    )
    obj = judgement_json(root, capsys)
    assert obj["rule_proposals"][0]["open"] is False
    assert obj["kinds"]["rule proposal"] == {"open": 0, "answered": 1}


def test_check_exit_codes_are_the_same_with_and_without_proposals(
    project: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4. Core imports Store in the source, so the rule would fail the check."""
    root, _prefix = project
    with_proposal = main(["--root", str(root), "check"])
    assert with_proposal == 0
    assert judgement_json(root, capsys)["rule_proposals"]
    edit_model(root, CORE_STORE, "Core keeps the work in sequence.")
    assert main(["--root", str(root), "refresh"]) == 0
    assert main(["--root", str(root), "check"]) == with_proposal
    assert judgement_json(root, capsys)["rule_proposals"] == []
    # The rule itself, when the author copies it into the model, makes the check fail.
    edit_model(root, "Core keeps the work in sequence.", CORE_STORE)
    rule = 'ImportRule("invariant-1", "forbid_import", ("Core",), ("Store",), invariant=1),'
    edit_model(root, "import_rules=()", f"import_rules=({rule})")
    assert main(["--root", str(root), "check"]) == 1
    assert "core imports" in capsys.readouterr().out
    assert judgement_json(root, capsys)["rule_proposals"] == []


# ---- the provider step -----------------------------------------------------------------

PROBABILITIES = {
    "forbid_import": 0.1,
    "allow_imports": 0.05,
    "forbid_cycle": 0.05,
    "no import rule": 0.8,
}


class Transport:
    """A Jev transport that counts the requests and gives the same choice to each question."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.states: list[Any] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        self.requests.append((method, path))
        if path == "/models":
            return {"models": [{"name": "jev-latest", "release_date": "2026-10-01"}]}
        assert body is not None
        self.states.append(body["state"])
        answer = {"choice": "no import rule", "confidence": 0.8, "probabilities": PROBABILITIES}
        return {
            "model": "jev-latest",
            "answers": {name: answer for name in body["questions"]},
            "usage": {},
        }

    def posts(self) -> int:
        return sum(path == "/systemone" for _method, path in self.requests)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Transport:
    sent = Transport()
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: sent)
    return sent


def test_without_the_option_no_request_goes_to_a_provider(
    project: tuple[Path, str], transport: Transport, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 5, for the text report and for `--json`."""
    root, _prefix = project
    assert main(["--root", str(root), "judgement"]) == 0
    judgement_json(root, capsys)
    assert transport.requests == []


def test_the_option_asks_only_the_invariants_without_a_proposal(
    project: tuple[Path, str], transport: Transport, capsys: pytest.CaptureFixture[str]
) -> None:
    """Invariant 1 has a pattern proposal. Only invariant 2 goes to the provider.

    The answer gives probabilities as information. It gives no proposal and no line.
    """
    root, _prefix = project
    plain = judgement_json(root, capsys)
    asked = judgement_json(root, capsys, "--propose-rules")
    assert transport.posts() == 1
    state = transport.states[0]
    assert state["invariant"] == {
        "n": 2,
        "text": "Api keeps one record of each request.",
        "governs": ["Api"],
    }
    assert [card["id"] for card in state["components"]] == ["Api"]
    found = asked.pop("rule_questions")
    assert asked == plain
    assert found["provider"] == "jev"
    assert found["proposal"] is False
    assert "no measured value" in found["reason"]
    assert found["questions"] == [
        {"map": "", "invariant": 2, "choice": "no import rule", "probabilities": PROBABILITIES}
    ]
    capsys.readouterr()
    assert main(["--root", str(root), "judgement", "--propose-rules"]) == 0
    out = capsys.readouterr().out
    assert "rule question: invariant 2: no import rule 0.80, forbid_import 0.10" in out
    assert "information only" in out


def test_a_provider_error_gives_the_cause_and_no_change(
    project: tuple[Path, str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _prefix = project
    monkeypatch.delenv(jev.KEY_ENV, raising=False)
    plain = judgement_json(root, capsys)
    asked = judgement_json(root, capsys, "--propose-rules")
    found = asked.pop("rule_questions")
    assert asked == plain
    assert found["questions"] == [] and found["error"]


def test_the_question_has_the_four_options() -> None:
    model = _model(Invariant(2, "Api keeps one record.", ("Api",)))
    tree = nest.Tree((nest.Map("", Path("map/model.py"), "map/model.py", model, _meaning(), {}),))
    found = rule_question.questions(tree)
    assert len(found) == 1
    q = found[0]
    assert isinstance(q, ChoiceQuestion)
    assert list(q.options) == ["forbid_import", "allow_imports", "forbid_cycle", "no import rule"]
    assert q.needs == tuple(q.options)


def _meaning() -> Any:
    from systemap.model import Meaning

    return Meaning(plain={})


def test_the_provider_option_without_propose_rules_is_an_error(
    project: tuple[Path, str], transport: Transport, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _prefix = project
    assert main(["--root", str(root), "judgement", "--provider", "openai"]) == 2
    assert "--propose-rules" in capsys.readouterr().err
    assert transport.requests == []
