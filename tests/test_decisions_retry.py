"""`systemap decisions`: retries, the CI result of an unknown request, counts, and the store.

Acceptance values (issue 89):

1. After one `insufficient_evidence` result, the request stays pending with
   `insufficient` 1, and the agent can send one more result. The second
   `insufficient_evidence` result makes the request `unknown`
   (`decisions_store.MAX_INSUFFICIENT` is 2). A later result for it is refused.
2. The store records each result. `decisions status --json` gives each result in
   `history`, with its verdict, summary, and citations. The text of `decisions status`
   gives each summary. This is also true when the second result is `supported`.
3. No output of `decisions submit`, `decisions status`, or `judgement` says that a person
   must examine an unknown request. The text and `open_lines` give the CI result: with an
   open judgement line, `judgement --strict` exits 1. Without one, the text says that
   `judgement --strict` does not exit 1 because of the request. `decisions status` exits 1.
4. `supported` in `decisions status` counts only the supported results of the current
   claims. After a map change opens the claim again, `supported` is 0 and
   `supported_records` is 1.
5. A citation of a test file that the facts list is accepted: a test file in the `tests`
   of a module record, and a test file in `test_file_issues`. A file that the facts do
   not list is refused.
6. A decision store without correct JSON, or that has an incorrect form, gives exit 1
   and an error with the path, the cause, and the instruction to remove the file.
7. Acceptance values 1 to 6 hold for a Python fixture and a TypeScript fixture.

The tests send no request to a model. They write the results that an agent would write.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree
from test_decisions import (
    CASES,
    FIXTURE,
    SOURCE,
    change_claim,
    cite,
    language,
    make_stale,
    of_type,
    of_type_absent,
    pending,
    run,
    submit,
)

from systemap.cli import main

PERSON = "person must"


@pytest.fixture(params=["python", "typescript"])
def mapped(
    request: pytest.FixtureRequest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> Path:
    """A mapped Python or TypeScript project with current facts, a test file that the
    facts list, and a test file that the parser cannot read."""
    if request.param == "python":
        tests = {
            "tests/test_reader.py": (
                "from pkg.reader import read\n\n\ndef test_read() -> None:\n"
                "    assert read('a') == 'a'\n"
            ),
            "tests/test_broken.py": "def (\n",
        }
        write_tree(tmp_path, {**SOURCE, **tests})
        init_two_cards(tmp_path, "--no-ci")
        assert main(["--root", str(tmp_path), "refresh"]) == 0
    else:
        shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
        broken = "import { x } from '../src/service';\nconst = ;\n"
        (tmp_path / "tests" / "broken.spec.ts").write_text(broken, encoding="utf-8")
        assert main(["--root", str(tmp_path), "refresh"]) == 0
    capsys.readouterr()
    return tmp_path


def verdict(
    request: dict[str, Any], name: str, summary: str, *cited: dict[str, Any]
) -> dict[str, Any]:
    return {
        "request_id": request["id"],
        "verdict": name,
        "citations": list(cited),
        "summary": summary,
    }


def status(root: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any], str]:
    code, out, _err = run(root, capsys, "decisions", "status", "--json")
    _code, text, _err = run(root, capsys, "decisions", "status")
    return code, json.loads(out), text


def two_insufficient(root: Path, capsys: pytest.CaptureFixture[str], card: str) -> tuple[str, str]:
    """Send two `insufficient_evidence` results for the review of a component.

    Give the request ID and the output of the second submit."""
    _card, name, _new = CASES[language(root)]
    first = of_type(pending(root, capsys), "source_review", card)
    code, out, err = submit(
        root, capsys, verdict(first, "insufficient_evidence", "First try.", cite(root, name))
    )
    assert code == 0, err
    assert f"insufficient_evidence: {first['id']}: insufficient_evidence verdict 1 of 2." in out
    second = of_type(pending(root, capsys), "source_review", card)
    assert second["id"] == first["id"] and second["insufficient"] == 1
    code, out, err = submit(root, capsys, verdict(second, "insufficient_evidence", "Second try."))
    assert code == 0, err
    return str(first["id"]), out


def test_insufficient_evidence_gives_one_more_attempt(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1, 2, and 7."""
    card, name, _new = CASES[language(mapped)]
    rid, out = two_insufficient(mapped, capsys, card)
    assert (
        f"unknown: {rid}: the claim has no decision after 2 insufficient_evidence verdicts." in out
    )
    assert of_type_absent(pending(mapped, capsys), card)
    request = {"id": rid}
    code, _out, err = submit(mapped, capsys, verdict(request, "contradicted", "Third try."))
    assert code == 1 and "is unknown" in err
    code, data, text = status(mapped, capsys)
    assert code == 1 and data["schema_version"] == 2
    row = data["unknown_requests"][0]
    assert row["id"] == rid and row["insufficient"] == 2
    history = row["history"]
    assert [h["verdict"] for h in history] == ["insufficient_evidence"] * 2
    assert [h["summary"] for h in history] == ["First try.", "Second try."]
    assert history[0]["citations"][0]["file"] == name and history[1]["citations"] == []
    assert "First try." in text and "Second try." in text


def test_a_second_result_can_be_supported_and_each_result_is_visible(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 2 and 7: the history keeps the first result after `supported`."""
    card, name, _new = CASES[language(mapped)]
    first = of_type(pending(mapped, capsys), "source_review", card)
    assert submit(mapped, capsys, verdict(first, "insufficient_evidence", "First try."))[0] == 0
    code, _out, err = submit(
        mapped, capsys, verdict(first, "supported", "The source agrees.", cite(mapped, name, 1, 2))
    )
    assert code == 0, err
    _code, data, text = status(mapped, capsys)
    record = next(r for r in data["records"] if r["id"] == first["id"])
    assert [h["verdict"] for h in record["history"]] == ["insufficient_evidence", "supported"]
    assert record["history"][1]["citations"][0]["end_line"] == 2
    assert "First try." in text and "The source agrees." in text


def test_an_unknown_request_gives_the_ci_result(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3 and 7: an open stale review line, and a missing review without a line."""
    card = make_stale(mapped, capsys)
    rid, out = two_insufficient(mapped, capsys, card)
    assert PERSON not in out and "systemap judgement --strict exits 1" in out
    code, data, text = status(mapped, capsys)
    assert code == 1 and PERSON not in text
    row = next(r for r in data["unknown_requests"] if r["id"] == rid)
    assert len(row["open_lines"]) == 1 and row["open_lines"][0].startswith("stale source review: ")
    assert "systemap judgement --strict exits 1" in text
    code, report = run(mapped, capsys, "judgement", "--strict", "--json")[:2]
    assert code == 1 and row["open_lines"][0] in [r["line"] for r in json.loads(report)["open"]]
    _code, report_text, _err = run(mapped, capsys, "judgement")
    assert PERSON not in report_text and f"unknown request {rid}" in report_text


def test_an_unknown_missing_review_without_a_line_gives_its_ci_result(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3 and 7: `require_reviews` is false, so a missing review has no line."""
    card, _name, _new = CASES[language(mapped)]
    rid, out = two_insufficient(mapped, capsys, card)
    assert PERSON not in out
    code, data, text = status(mapped, capsys)
    row = next(r for r in data["unknown_requests"] if r["id"] == rid)
    assert code == 1 and row["open_lines"] == []
    assert "does not exit 1 because of this claim" in text
    assert "[judgement] require_reviews = true" in text


def test_supported_counts_only_the_current_claims(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4 and 7."""
    card, name, _new = CASES[language(mapped)]
    request = of_type(pending(mapped, capsys), "source_review", card)
    code, _out, err = submit(
        mapped, capsys, verdict(request, "supported", "Agrees.", cite(mapped, name))
    )
    assert code == 0, err
    _code, data, _text = status(mapped, capsys)
    assert data["supported"] == 1
    change_claim(mapped, card)
    _code, data, text = status(mapped, capsys)
    assert data["supported"] == 0
    assert data["supported_records"] == 1
    assert ", 0 supported," in text


@pytest.mark.parametrize("kind", ["listed", "issue", "not listed"])
def test_a_test_file_that_the_facts_list_can_be_cited(
    mapped: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    """Acceptance 5 and 7."""
    python = language(mapped) == "python"
    name = {
        "listed": "tests/test_reader.py" if python else "tests/service.spec.ts",
        "issue": "tests/test_broken.py" if python else "tests/broken.spec.ts",
        "not listed": "systemap.toml",
    }[kind]
    requests = pending(mapped, capsys)
    # `judgement` gives no line about a test file (issue 114). Thus no request is about one.
    assert not [r for r in requests if "test file" in r["target"]]
    request = of_type(requests, "source_review")
    code, _out, err = submit(
        mapped, capsys, verdict(request, "contradicted", "Read.", cite(mapped, name))
    )
    if kind == "not listed":
        assert code == 1 and f"{name} is not a source file or a test file in the facts." in err
        return
    assert code == 0, err


@pytest.mark.parametrize(
    ("text", "cause"),
    [
        ("{not json", "it does not contain correct JSON"),
        ('{"version": 99, "records": {}}', "it has a different version or form"),
        ("[]", "it has a different version or form"),
    ],
)
def test_a_damaged_store_gives_an_error(
    mapped: Path, capsys: pytest.CaptureFixture[str], text: str, cause: str
) -> None:
    """Acceptance 6 and 7."""
    store = mapped / ".systemap" / "decisions.json"
    store.parent.mkdir(exist_ok=True)
    store.write_text(text, encoding="utf-8")
    for argv in (("decisions", "status"), ("decisions", "pending"), ("judgement",)):
        code, _out, err = run(mapped, capsys, *argv)
        assert code == 1, argv
        assert str(store) in err and cause in err and "Remove the file" in err
    assert store.read_text(encoding="utf-8") == text
