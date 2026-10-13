"""The decision requests contain all the claims of their digest, and bad input gives an error.

Acceptance values:

1. decisions-1: each string value in `card_review.claims` of a component is in the claim of
   its `source_review` request. A change of only `Step.say` changes the claim. A sequence
   that names the component only in `starts` is in the claim. A Python fixture and a
   TypeScript fixture.
2. decisions-2: the drift question of a component contains the same sequences as
   `card_review.claims`, also a sequence that names the component only in `starts`.
3. decisions-3: a `supported` flow result that cites only a file that is not in the two
   endpoint components is refused with exit 1, and no file changes. A citation of an
   endpoint file is accepted. A Python fixture and a TypeScript fixture.
4. decisions-4: a result file that is not UTF-8 gives exit 1 and a message with the file
   name and the cause. A store that is not UTF-8 gives exit 1 and a message with the store
   path for `decisions pending` and `judgement`. No traceback.
5. decisions-5: an OpenAI answer with a list where a string must be (`choice`, `value`, or
   `name`) gives an `OpenAIError` or a new request. It does not give a `TypeError`.

No test sends a request to Jev or OpenAI. The OpenAI transport is a function in this file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import card_review, config, decisions, drift_order, facts_file, judgement_json, nest
from systemap import openai_provider as oa
from systemap.cli import main
from systemap.decision import ChoiceAnswer, ChoiceQuestion, PredicateQuestion
from systemap.model import Component, Journey, Meaning, Model, Step

FIXTURE = Path(__file__).parent / "fixtures" / "typescript-app"
PY_SOURCE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
    "pkg/ledger.py": "def keep(record: str) -> str:\n    return record\n",
}
# The modules and the first file of Reader, Writer, and Ledger, for each language.
MODULES = {
    "python": (("pkg.reader",), ("pkg.writer",), ("pkg.ledger",)),
    "typescript": (
        ("acme.web.cli",),
        ("acme.web.service",),
        ("acme.web.view", "acme.web.client", "acme.web.index"),
    ),
}
FILES = {
    "python": ("pkg/reader.py", "pkg/writer.py", "pkg/ledger.py"),
    "typescript": ("src/cli.ts", "src/service.ts", "src/view.tsx"),
}
SAY = "The writer keeps one record in the ledger."

MODEL = """from systemap.model import (
    Component, Container, Flow, Journey, Meaning, Model, Region, Step,
)

CONTAINERS = (Container(id="system", label="SYSTEM", box=(20, 20, 600, 300), tone="server"),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 560, 220), container="system"),)
COMPONENTS = (
    Component(id="Reader", does="Reads the input.", implemented_by={reader!r},
              kind="component", note="The reader note.", region="core", x=80, y=120),
    Component(id="Writer", does="Writes the result.", implemented_by={writer!r},
              region="core", x=260, y=120),
    Component(id="Ledger", does="Keeps the records.", implemented_by={ledger!r},
              region="core", x=440, y=120),
)
MODEL = Model(
    canvas=(640, 340),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=(Flow("Reader", "Writer", "request", "data", source_refs={refs!r}),),
    flow_kinds=(),
    invariants=(),
)
MEANING = Meaning(
    plain={{"Reader": "the reader", "Writer": "the writer", "Ledger": "the ledger"}},
    journeys=(
        Journey(
            id="keep-record",
            label="A record goes to the ledger",
            starts="Reader",
            steps=(Step(acts=("Writer",), measures=(), say={say!r}),),
        ),
    ),
)
"""


@pytest.fixture(params=["python", "typescript"])
def project(
    request: pytest.FixtureRequest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> Path:
    """A project with Reader, Writer, and Ledger, a Reader-to-Writer flow, and current facts.

    The flow cites a Reader module and a Ledger module.
    """
    if request.param == "python":
        write_tree(tmp_path, PY_SOURCE)
        assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    else:
        shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    (tmp_path / "map" / "model.py").write_text(model_text(request.param, ()), encoding="utf-8")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    cfg = config.load(tmp_path)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    reader, _writer, ledger = MODULES[request.param]
    refs = tuple(f"{m}@{facts['components'][m]['source_sha256']}" for m in (reader[0], ledger[0]))
    (tmp_path / "map" / "model.py").write_text(model_text(request.param, refs), encoding="utf-8")
    (tmp_path / "language").write_text(request.param, encoding="utf-8")
    capsys.readouterr()
    return tmp_path


def model_text(language: str, refs: tuple[str, ...], say: str = SAY) -> str:
    reader, writer, ledger = MODULES[language]
    return MODEL.format(reader=reader, writer=writer, ledger=ledger, refs=refs, say=say)


def language_of(root: Path) -> str:
    return (root / "language").read_text(encoding="utf-8")


def run(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["--root", str(root), *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def current_requests(root: Path) -> list[decisions.Request]:
    cfg = config.load(root)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    return decisions.requests(tree, facts, cfg.root, judgement_json.evaluate(tree, facts, cfg))


def strings(value: Any) -> list[str]:
    """Give each string value in a claim record."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings(item)]
    if isinstance(value, list | tuple):
        return [s for item in value for s in strings(item)]
    return []


# ---- decisions-1 -------------------------------------------------------------------


def test_a_component_request_contains_each_claim_of_its_digest(project: Path) -> None:
    """Acceptance 1: each string claim value is in the request claim."""
    cfg = config.load(project)
    m = nest.load(cfg).top
    found = {r.target: r for r in current_requests(project) if r.type == decisions.SOURCE_REVIEW}
    for card in m.model.components:
        claim = found[card.id].claim
        missing = [
            s for s in strings(card_review.claims(card, m.model, m.meaning)) if s not in claim
        ]
        assert not missing, (card.id, missing)
    # Reader is only the start of the sequence. Writer is only an actor of its step.
    assert SAY in found["Reader"].claim and SAY in found["Writer"].claim


def test_a_change_of_only_the_step_text_changes_the_request_claim(project: Path) -> None:
    """Acceptance 1: the digest and the claim change together."""
    before = {r.target: r for r in current_requests(project) if r.type == decisions.SOURCE_REVIEW}
    model = project / "map" / "model.py"
    model.write_text(model.read_text(encoding="utf-8").replace(SAY, "The writer stops."))
    after = {r.target: r for r in current_requests(project) if r.type == decisions.SOURCE_REVIEW}
    for card in ("Reader", "Writer"):
        assert before[card].digest != after[card].digest
        assert before[card].claim != after[card].claim
        assert "The writer stops." in after[card].claim


# ---- decisions-2 -------------------------------------------------------------------


def test_the_drift_question_has_the_sequences_of_the_review_digest() -> None:
    """Acceptance 2: a sequence that starts at Reader is a claim of Reader."""
    cards = tuple(Component(id=name, does=f"{name} works.") for name in ("Reader", "Writer"))
    model = Model(
        canvas=(10, 10),
        containers=(),
        regions=(),
        components=cards,
        flows=(),
        flow_kinds=(),
        invariants=(),
    )
    step = Step(acts=("Writer",), measures=(), say=SAY)
    meaning = Meaning(plain={}, journeys=(Journey("keep", "Keep", (step,), starts="Reader"),))
    for card in cards:
        drift = drift_order.claims_of(card, model, meaning)["sequences"]
        assert drift == card_review.claims(card, model, meaning)["journeys"]
        assert [s["id"] for s in drift] == ["keep"]


# ---- decisions-3 -------------------------------------------------------------------


def cite(root: Path, name: str) -> dict[str, Any]:
    digest = decisions.file_digest(root / name)
    return {"file": name, "start_line": 1, "end_line": 1, "sha256": digest}


def submit(root: Path, capsys: pytest.CaptureFixture[str], *results: Any) -> tuple[int, str, str]:
    path = root.parent / f"{root.name}-results.json"
    path.write_text(json.dumps(list(results)), encoding="utf-8")
    return run(root, capsys, "decisions", "submit", str(path))


def files_of(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "node_modules" not in p.parts
    }


def test_a_flow_result_must_cite_an_endpoint_file(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3: the Ledger file is a file of a source record, not of an endpoint."""
    _reader, writer, ledger = FILES[language_of(project)]
    flow = next(r for r in current_requests(project) if r.type == decisions.FLOW_REVIEW)
    assert ledger in {f.file for f in flow.files}
    item = {"request_id": flow.id, "verdict": "supported", "summary": "The source agrees."}
    before = files_of(project)
    code, _out, err = submit(project, capsys, {**item, "citations": [cite(project, ledger)]})
    assert code == 1 and "file of an endpoint component" in err, err
    assert files_of(project) == before
    code, out, err = submit(project, capsys, {**item, "citations": [cite(project, writer)]})
    assert code == 0, err
    assert "review: flow Reader->Writer" in out


# ---- decisions-4 -------------------------------------------------------------------


def test_a_result_file_that_is_not_utf8_gives_an_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4: exit 1 with the file name and the cause, and no traceback."""
    path = project.parent / "results-utf16.json"
    path.write_text("[]", encoding="utf-16")
    code, _out, err = run(project, capsys, "decisions", "submit", str(path))
    assert code == 1
    assert str(path) in err and "UTF-8" in err


def test_a_store_that_is_not_utf8_gives_an_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4: `decisions pending` and `judgement` give exit 1 with the store path."""
    store = project / ".systemap" / "decisions.json"
    store.parent.mkdir(exist_ok=True)
    store.write_text(json.dumps({"version": 1, "records": {}}), encoding="utf-16")
    for argv in (("decisions", "pending"), ("judgement",)):
        code, _out, err = run(project, capsys, *argv)
        assert code == 1, argv
        assert "decisions.json" in err and "UTF-8" in err, err


# ---- decisions-5 -------------------------------------------------------------------

STATE = {"module": "pkg.reader"}
OWNER = ChoiceQuestion(
    "m1",
    "owner",
    "Which component owns `module`?",
    STATE,
    {"intake": "Reads.", "report": "Writes."},
)
GOOD = {
    "type": "choice",
    "name": "owner",
    "choice": "intake",
    "probabilities": [{"value": "intake", "probability": 1.0}],
    "confidence": 1.0,
}


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "choice": []},
        {**GOOD, "probabilities": [{"value": [], "probability": 1.0}]},
    ],
)
def test_a_cached_answer_of_an_incorrect_type_is_asked_again(bad: dict[str, Any]) -> None:
    """Acceptance 5: the cached answer is not used, and the provider sends a new request."""
    with pytest.raises(oa.OpenAIError):
        oa.answer_of(OWNER, bad)
    sent: list[Any] = []

    def send(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        sent.append(body)
        return {"model": "gpt-6-luna", "answers": [GOOD]}

    provider = oa.OpenAIProvider(send)
    provider.cache.entries[oa.cache_key(provider.model, OWNER)] = bad
    assert provider.pending([OWNER]) == 1
    assert provider.decide([OWNER]) == [ChoiceAnswer("intake", {"intake": 1.0}, 1.0, GOOD)]
    assert len(sent) == 1


def test_an_answer_name_of_an_incorrect_type_gives_an_openai_error() -> None:
    """Acceptance 5: an answer with a list as its name is not an answer to the question."""
    reads = PredicateQuestion("m1", "reads", "Does `module` read files?", STATE)
    bad = {"type": "predicate", "name": [], "probability": 0.5}
    provider = oa.OpenAIProvider(lambda m, p, b: {"answers": [bad]})
    with pytest.raises(oa.OpenAIError, match="no answer to reads"):
        provider.decide([reads])
