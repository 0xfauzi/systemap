"""`systemap judgement --order-by-drift`: put the stale source review lines in sequence.

Acceptance values:

1. With an injected provider that gives fixed probabilities, the stale lines are in
   ascending sequence by probability. A Python fixture and a TypeScript fixture.
2. The open lines, the exit codes, and the answers are identical with and without the
   option, for the text report and for `--json`.
3. Without the option, the command sends zero requests. An injected transport counts them.
4. A refusal puts its line at the end with "no score", and the report gives the count of
   questions without a score. A failed request gives "no score" for each line.
5. A second run with the option sends zero questions: the answers come from the cache.

No test calls Jev. The transport is a function in this file.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import card_review, config, drift_order, facts_file, jev, judgement, nest
from systemap.cli import main
from systemap.decision import (
    Answer,
    DecisionError,
    PredicateAnswer,
    Question,
    Refusal,
)

TS_MODEL = """from systemap.model import Component, Container, Meaning, Model, Region

CONTAINERS = (Container(id="system", label="SYSTEM", box=(20, 20, 600, 300), tone="server"),)

REGIONS = (
    Region(id="application", label="APPLICATION", box=(40, 60, 560, 220), container="system"),
)

COMPONENTS = (
    Component(
        id="Front",
        does="Serves a user through the command line and web view.",
        implemented_by=("acme.web.cli", "acme.web.index", "acme.web.view"),
        entry="serve",
        region="application",
        x=100,
        y=120,
    ),
    Component(
        id="Service",
        does="Gives the data to the command line and the web view.",
        implemented_by=("acme.web.client", "acme.web.service"),
        region="application",
        x=380,
        y=120,
    ),
)

MODEL = Model(
    canvas=(640, 340),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=(),
    flow_kinds=(),
    invariants=(),
)

MEANING = Meaning(plain={"Front": "the front", "Service": "the service"})
"""

# The source change after the review, for each language: a new function in each module.
PY_CHANGE = {
    "pkg/reader.py": "\n\ndef count(source: str) -> int:\n    return len(source)\n",
    "pkg/writer.py": "\n\ndef close() -> None:\n    return None\n",
}
TS_CHANGE = {
    "src/service.ts": "\nexport function count(text: string): number {\n  return text.length;\n}\n",
    "src/cli.ts": "\nexport function stop(): void {\n  return;\n}\n",
}
# Fixed probabilities by component: the lowest goes first.
PY_SCORES = {"Reader": 0.8, "Writer": 0.1}
TS_SCORES = {"Front": 0.6, "Service": 0.3}


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=t@example.invalid"]
        + list(args),
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def record_reviews(root: Path) -> None:
    """Write the current digest of each component into the model file."""
    cfg = config.load(root)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    path = root / "map/model.py"
    text = path.read_text(encoding="utf-8")
    for card in tree.top.model.components:
        digest = card_review.digest(card, tree.top.model, tree.top.meaning, facts)
        assert digest is not None
        text = text.replace(f'id="{card.id}",', f'id="{card.id}", source_review="{digest}",', 1)
    path.write_text(text, encoding="utf-8")


def change(root: Path, files: dict[str, str]) -> None:
    for rel, tail in files.items():
        path = root / rel
        path.write_text(path.read_text(encoding="utf-8") + tail, encoding="utf-8")
    assert main(["--root", str(root), "extract"]) == 0


def stale_project(root: Path, language: str, capsys: pytest.CaptureFixture[str]) -> Path:
    """A reviewed project in a Git commit, with a source change after the review."""
    if language == "python":
        write_tree(root, {**STARTER_MODULES, "pkg/__init__.py": ""})
        init_two_cards(root, "--no-ci")
    else:
        shutil.copytree(Path(__file__).parent / "fixtures/typescript-app", root, dirs_exist_ok=True)
        (root / "map/model.py").write_text(TS_MODEL, encoding="utf-8")
    assert main(["--root", str(root), "extract"]) == 0
    record_reviews(root)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "reviewed")
    change(root, PY_CHANGE if language == "python" else TS_CHANGE)
    capsys.readouterr()
    return root


@pytest.fixture(params=["python", "typescript"])
def stale(
    request: pytest.FixtureRequest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[Path, dict[str, float]]:
    root = stale_project(tmp_path, request.param, capsys)
    return root, PY_SCORES if request.param == "python" else TS_SCORES


class Fixed:
    """A decision provider with a fixed probability for each component. None is a refusal."""

    name = "fixed"

    def __init__(self, scores: dict[str, float | None]) -> None:
        self.scores = scores
        self.asked: list[Question] = []

    def decide(self, questions: Sequence[Question]) -> list[Answer]:
        self.asked += questions
        out: list[Answer] = []
        for q in questions:
            found = self.scores[q.state["component"]["id"]]
            out.append(Refusal("no decision") if found is None else PredicateAnswer(found))
        return out


class Transport:
    """A Jev transport that counts the requests and answers each question from `scores`."""

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.requests: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        self.requests.append((method, path))
        if path == "/models":
            return {"models": [{"name": "jev-latest", "release_date": "2026-10-01"}]}
        assert body is not None
        found = self.scores[body["state"]["component"]["id"]]
        answers = {name: {"noul": found} for name in body["questions"]}
        return {"model": "jev-latest", "answers": answers, "usage": {}}

    def posts(self) -> int:
        return sum(path == "/systemone" for _method, path in self.requests)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Transport:
    sent = Transport({**PY_SCORES, **TS_SCORES})
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: sent)
    return sent


def loaded(root: Path) -> tuple[config.Config, nest.Tree, dict[str, Any], list[str]]:
    cfg = config.load(root)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    lines = judgement.run_tree(tree, facts)
    return cfg, tree, facts, lines


def stale_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if judgement.kind_of(line) == "stale source review"]


def card_of(line: str) -> str:
    return line.removeprefix("stale source review: ").split(" ", 1)[0]


def judgement_run(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = main(["--root", str(root), "judgement", *argv])
    return code, capsys.readouterr().out


def open_rows(out: str) -> list[str]:
    """The open lines of the text report, in their sequence, without the indent."""
    notices = ("stale answer: ", "pending answer: ", "policy answer: ")
    return [
        row[2:]
        for row in out.splitlines()
        if row.startswith("  ") and not row.startswith("   ") and not row[2:].startswith(notices)
    ]


# ---- acceptance 1 -----------------------------------------------------------------


def test_the_stale_lines_are_in_ascending_sequence_by_probability(
    stale: tuple[Path, dict[str, float]],
) -> None:
    """Acceptance 1 for a Python fixture and a TypeScript fixture."""
    root, scores = stale
    cfg, tree, facts, lines = loaded(root)
    assert len(stale_lines(lines)) == 2
    found = drift_order.order(cfg, tree, facts, lines, lambda: Fixed(dict(scores)))
    ordered = found.ordered(lines)
    assert [card_of(line) for line in stale_lines(ordered)] == sorted(
        scores, key=lambda c: scores[c]
    )
    assert sorted(ordered) == sorted(lines)
    # The other lines keep their positions.
    assert [x for x in ordered if x not in found.scores] == [
        x for x in lines if x not in found.scores
    ]
    assert found.no_score == 0


def test_the_text_and_the_json_give_the_probability_of_each_stale_line(
    stale: tuple[Path, dict[str, float]],
    transport: Transport,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Acceptance 1 through the command, with an injected transport."""
    root, scores = stale
    code, out = judgement_run(root, capsys, "--order-by-drift", "--brief")
    assert code == 0
    rows = out.splitlines()
    first, second = sorted(scores, key=lambda c: scores[c])
    lows = [i for i, row in enumerate(rows) if row.startswith("  stale source review: ")]
    assert [card_of(rows[i][2:]) for i in lows] == [first, second]
    assert [rows[i + 1] for i in lows] == [
        f"    drift score: {scores[first]:.2f}",
        f"    drift score: {scores[second]:.2f}",
    ]
    code = main(["--root", str(root), "judgement", "--json", "--order-by-drift"])
    obj = json.loads(capsys.readouterr().out)
    items = [row for row in obj["open"] if row["kind"] == "stale source review"]
    assert [row["drift"]["probability"] for row in items] == [scores[first], scores[second]]
    assert all(row["drift"]["source"] == "diff" for row in items)
    assert obj["drift_order"] == {"questions": 2, "no_score": 0, "reason": ""}
    assert all("drift" not in row for row in obj["open"] if row not in items)


# ---- acceptance 2 and 3 -----------------------------------------------------------


@pytest.mark.parametrize("strict", [False, True])
def test_open_lines_exit_codes_and_answers_do_not_change(
    stale: tuple[Path, dict[str, float]],
    transport: Transport,
    capsys: pytest.CaptureFixture[str],
    strict: bool,
) -> None:
    """Acceptance 2 for the text report and for the JSON object."""
    root, _scores = stale
    extra = ["--strict"] if strict else []
    plain_code, plain = judgement_run(root, capsys, "--brief", *extra)
    drift_code, drift = judgement_run(root, capsys, "--brief", "--order-by-drift", *extra)
    assert drift_code == plain_code == (1 if strict else 0)
    assert sorted(open_rows(drift)) == sorted(open_rows(plain))
    assert plain.splitlines()[0] == drift.splitlines()[0]
    code_a = main(["--root", str(root), "judgement", "--json", *extra])
    a = json.loads(capsys.readouterr().out)
    code_b = main(["--root", str(root), "judgement", "--json", "--order-by-drift", *extra])
    b = json.loads(capsys.readouterr().out)
    assert code_a == code_b == (1 if strict else 0)
    assert sorted(r["line"] for r in a["open"]) == sorted(r["line"] for r in b["open"])
    for key in ("answered", "stale_answers", "source_reviews", "kinds"):
        assert a[key] == b[key]


def test_without_the_option_no_request_is_sent(
    stale: tuple[Path, dict[str, float]],
    transport: Transport,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Acceptance 3: a key is set, and the command without the option sends 0 requests."""
    root, _scores = stale
    judgement_run(root, capsys, "--brief")
    judgement_run(root, capsys, "--json")
    judgement_run(root, capsys, "--strict")
    assert transport.requests == []


def test_without_a_stale_line_the_option_sends_no_request(
    tmp_path: Path, transport: Transport, capsys: pytest.CaptureFixture[str]
) -> None:
    root = stale_project(tmp_path, "python", capsys)
    record_reviews_again(root)
    code, out = judgement_run(root, capsys, "--brief", "--order-by-drift")
    assert code == 0
    assert "drift sequence: No stale source review line is open. No question was sent." in out
    assert transport.requests == []


def record_reviews_again(root: Path) -> None:
    path = root / "map/model.py"
    path.write_text(
        re.sub(r' source_review="\w*",', "", path.read_text(encoding="utf-8")), encoding="utf-8"
    )
    record_reviews(root)


# ---- acceptance 4 -----------------------------------------------------------------


def test_a_refusal_puts_its_line_at_the_end_with_no_score(
    stale: tuple[Path, dict[str, float]],
) -> None:
    """Acceptance 4: the lowest component gets a refusal and goes to the end."""
    root, scores = stale
    cfg, tree, facts, lines = loaded(root)
    low, high = sorted(scores, key=lambda c: scores[c])
    given: dict[str, float | None] = {low: None, high: scores[high]}
    found = drift_order.order(cfg, tree, facts, lines, lambda: Fixed(given))
    assert [card_of(line) for line in stale_lines(found.ordered(lines))] == [high, low]
    rows = found.rows()
    assert [rows[line] for line in stale_lines(found.ordered(lines))] == [
        [f"drift score: {scores[high]:.2f}"],
        ["drift score: no score"],
    ]
    assert found.no_score == 1
    assert found.notes()[-1] == (
        "drift sequence: 1 of 2 questions got no score. Cause: the decision provider gave a refusal"
    )


class Failing:
    name = "failing"

    def decide(self, questions: Sequence[Question]) -> list[Answer]:
        raise DecisionError("the request failed")


def test_a_failed_request_gives_no_score_and_the_count(
    stale: tuple[Path, dict[str, float]],
) -> None:
    """Acceptance 4 for a failed request. No other value replaces the score."""
    root, _scores = stale
    cfg, tree, facts, lines = loaded(root)
    found = drift_order.order(cfg, tree, facts, lines, Failing)
    assert found.ordered(lines) == lines
    assert all(rows == ["drift score: no score"] for rows in found.rows().values())
    assert found.notes()[-1] == (
        "drift sequence: 2 of 2 questions got no score. Cause: the request failed"
    )


def test_without_a_key_the_lines_get_no_score_and_the_exit_code_stays(
    stale: tuple[Path, dict[str, float]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _scores = stale
    monkeypatch.delenv(jev.KEY_ENV, raising=False)
    code, out = judgement_run(root, capsys, "--brief", "--strict", "--order-by-drift")
    assert code == 1
    assert out.count("    drift score: no score") == 2
    assert "drift sequence: 2 of 2 questions got no score. Cause: set TYPESAFE_API_KEY" in out


# ---- acceptance 5 -----------------------------------------------------------------


def test_a_second_run_sends_no_question(
    stale: tuple[Path, dict[str, float]],
    transport: Transport,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Acceptance 5. The model list request is the release date read, with no model tokens."""
    root, _scores = stale
    judgement_run(root, capsys, "--brief", "--order-by-drift")
    assert transport.posts() == 2
    judgement_run(root, capsys, "--brief", "--order-by-drift")
    assert transport.posts() == 2


# ---- the source part --------------------------------------------------------------


def test_the_source_part_is_the_diff_since_the_reviewed_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = stale_project(tmp_path, "python", capsys)
    cfg, tree, facts, lines = loaded(root)
    asked = Fixed(dict(PY_SCORES))
    drift_order.order(cfg, tree, facts, lines, lambda: asked)
    by_card = {q.state["component"]["id"]: q for q in asked.asked}
    reader = by_card["Reader"]
    assert reader.instructions == drift_order.DIFF_Q
    assert reader.state["source"]["form"] == "diff"
    assert "+def count(source: str) -> int:" in reader.state["source"]["text"]
    assert "pkg/writer.py" not in reader.state["source"]["text"]
    assert reader.state["component"]["does"] == "Reads the input and turns it into a request."
    assert [f["to"] for f in reader.state["flows"]] == ["Writer"]


def test_without_the_reviewed_commit_the_source_part_is_the_text_up_to_the_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = stale_project(tmp_path, "python", capsys)
    # A rename, not rmtree: Git object files are read-only, and Windows refuses to remove them.
    (root / ".git").rename(tmp_path / "git-gone")
    change(root, {"pkg/reader.py": "\n# " + "x" * (drift_order.CAP + 10) + "\n"})
    cfg, tree, facts, lines = loaded(root)
    asked = Fixed(dict(PY_SCORES))
    drift_order.order(cfg, tree, facts, lines, lambda: asked)
    by_card = {q.state["component"]["id"]: q for q in asked.asked}
    reader, writer = by_card["Reader"].state["source"], by_card["Writer"].state["source"]
    assert by_card["Reader"].instructions == drift_order.TEXT_Q
    assert reader["form"] == "text" and reader["cut"] is True
    assert len(reader["text"]) == drift_order.CAP
    assert reader["text"].startswith("=== pkg/reader.py\ndef read(source: str) -> str:")
    assert writer["form"] == "text" and writer["cut"] is False
