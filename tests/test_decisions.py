"""`systemap decisions`: a coding agent examines the semantic claims, and systemap records them.

Acceptance values:

1. A result with a citation to a file outside the repository, a stale sha256, a line span
   past the end of the file, or an unknown request ID is refused with exit 1. No file in
   the project changes, and the store is not written.
2. A valid `supported` result for a stale component review makes `card_review.state`
   `current`, and `judgement --json` gives one fewer `stale source review` line.
3. A valid `supported` result for an open judgement line closes that line in
   `judgement --strict`. The answer keeps the citations.
4. Three `contradicted` results for one target make the request `unknown`, also with a map
   change between each result. A map change does not make the unknown request pending.
   A change of the source of the target makes the request pending again, with zero
   attempts.
5. One `insufficient_evidence` result makes the request `unknown` at once.
6. Acceptance values 1 to 5 hold for a Python fixture and a TypeScript fixture.
7. `[judgement] require_reviews = true` makes `judgement --strict` fail on a missing source
   review. The JSON output gives the setting. The default is false.
8. The IDs of `decisions pending` are the same in a second call if no claim changes.
9. The store identity of a judgement request is the finding kind and the names in the line.
   If two current lines have the same kind and names, the identity of each is its line.

The tests send no request to a model. They write the results that an agent would write.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import card_review, config, decisions, extract, nest
from systemap.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "typescript-app"
SOURCE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "from pkg.reader import read\n\n\ndef write(request: str) -> str:\n    return read(request)\n",
}
# The component, its first source file, and a source change for each language.
CASES = {
    "python": (
        "Reader",
        "pkg/reader.py",
        "def read(source: str) -> str:\n    return source.strip()\n",
    ),
    "typescript": ("Application", "src/service.ts", None),
}


@pytest.fixture(params=["python", "typescript"])
def project(
    request: pytest.FixtureRequest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> Path:
    """A mapped Python project or a mapped TypeScript project, with current facts."""
    if request.param == "python":
        write_tree(tmp_path, SOURCE)
        init_two_cards(tmp_path, "--no-ci")
        assert main(["--root", str(tmp_path), "extract"]) == 0
    else:
        shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
        assert main(["--root", str(tmp_path), "refresh"]) == 0
    capsys.readouterr()
    return tmp_path


def language(root: Path) -> str:
    return config.load(root).language


def run(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["--root", str(root), *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def pending(root: Path, capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    code, out, _err = run(root, capsys, "decisions", "pending", "--json")
    assert code == 0
    return list(json.loads(out)["requests"])


def judged(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, Any]:
    code, out, _err = run(root, capsys, "judgement", "--json", *argv)
    return code, json.loads(out)


def cite(root: Path, name: str, start: int = 1, end: int = 1) -> dict[str, Any]:
    """A citation as an agent writes it: the span and the digest of the full file."""
    digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
    return {"file": name, "start_line": start, "end_line": end, "sha256": digest}


def submit(
    root: Path, capsys: pytest.CaptureFixture[str], *results: dict[str, Any]
) -> tuple[int, str, str]:
    path = root.parent / f"{root.name}-results.json"
    path.write_text(json.dumps(list(results)), encoding="utf-8")
    return run(root, capsys, "decisions", "submit", str(path))


def result(request: dict[str, Any], verdict: str, *citations: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request["id"],
        "verdict": verdict,
        "citations": list(citations),
        "summary": "The source agrees with the claim." if verdict == "supported" else "No.",
    }


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "node_modules" not in p.parts
    }


def of_type(requests: list[dict[str, Any]], kind: str, target: str = "") -> dict[str, Any]:
    return next(r for r in requests if r["type"] == kind and (not target or r["target"] == target))


def make_stale(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    """Record the review of the first component, then change its source. Give the component."""
    card, name, new = CASES[language(root)]
    assert run(root, capsys, "review", card)[0] == 0
    path = root / name
    path.write_text(new or path.read_text(encoding="utf-8") + "\nexport const added = 1;\n")
    assert run(root, capsys, "extract")[0] == 0
    return card


def card_state(root: Path, card_id: str) -> str:
    cfg = config.load(root)
    m = nest.load(cfg).top
    card = m.model.component(card_id)
    assert card is not None
    return card_review.state(card, m.model, m.meaning, extract.build(cfg))


def test_pending_gives_stable_requests_with_claims_and_files(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 8, and the fields of each request."""
    first = pending(project, capsys)
    assert first == pending(project, capsys)
    card, name, _new = CASES[language(project)]
    review = of_type(first, "source_review", card)
    assert review["id"].startswith(f"source_review:{card}@")
    assert review["verdicts"] == ["supported", "contradicted", "insufficient_evidence"]
    files = {f["file"]: f["sha256"] for f in review["files"]}
    assert files[name] == cite(project, name)["sha256"]
    lines = [r for r in first if r["type"] == "judgement"]
    assert lines and all(r["claim"] == r["target"] for r in lines)


@pytest.mark.parametrize(
    "fault", ["outside", "dots", "symlink", "stale sha256", "past the end", "unknown id"]
)
def test_an_incorrect_result_is_refused_and_nothing_changes(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    fault: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Acceptance 1 and 6: exit 1, an error that names the fault, and no file change."""
    card, name, _new = CASES[language(project)]
    request = of_type(pending(project, capsys), "source_review", card)
    citation = cite(project, name)
    outside = tmp_path_factory.mktemp("outside") / "secret.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    if fault == "outside":
        citation = {**cite(outside.parent, "secret.py"), "file": str(outside)}
    elif fault == "dots":
        citation = {
            **cite(outside.parent, "secret.py"),
            "file": f"../{outside.parent.name}/secret.py",
        }
    elif fault == "symlink":
        os.symlink(outside, project / "link.py")
        citation = cite(project, "link.py")
    elif fault == "stale sha256":
        citation["sha256"] = "0" * 64
    elif fault == "past the end":
        count = len((project / name).read_bytes().splitlines())
        citation = {**citation, "start_line": count, "end_line": count + 1}
    else:
        request = {**request, "id": "source_review:Nothing@0000000000000000"}
    before = snapshot(project)
    code, _out, err = submit(project, capsys, result(request, "supported", citation))
    assert code == 1
    words = {
        "outside": "relative to the repository root",
        "dots": "without '..'",
        "symlink": "outside the repository",
        "stale sha256": "is not the digest of the current",
        "past the end": "are not in",
        "unknown id": "is not a current decision request",
    }[fault]
    assert words in err and "The command wrote nothing." in err
    assert snapshot(project) == before
    assert not (project / ".systemap" / "decisions.json").exists()


def test_supported_needs_a_citation_in_a_file_of_the_claim(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A supported result without a citation, or with a citation outside the claim, is refused."""
    card, _name, _new = CASES[language(project)]
    request = of_type(pending(project, capsys), "source_review", card)
    before = snapshot(project)
    code, _out, err = submit(project, capsys, result(request, "supported"))
    assert code == 1 and "one or more citations" in err
    assert snapshot(project) == before


def test_supported_makes_a_stale_review_current(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 2 and 6: the state becomes current, and judgement has one fewer stale review."""
    card = make_stale(project, capsys)
    _card, name, _new = CASES[language(project)]
    assert card_state(project, card) == card_review.STALE
    _code, before = judged(project, capsys)
    request = of_type(pending(project, capsys), "source_review", card)
    code, out, err = submit(
        project, capsys, result(request, "supported", cite(project, name, 1, 2))
    )
    assert code == 0, err
    assert f"review: component {card}" in out
    assert card_state(project, card) == card_review.CURRENT
    _code, after = judged(project, capsys)
    stale = "stale source review"
    assert after["kinds"][stale]["open"] == before["kinds"][stale]["open"] - 1 == 0
    assert after["source_reviews"]["stale"] == before["source_reviews"]["stale"] - 1


def test_supported_closes_a_judgement_line(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3 and 6: the line closes in judgement --strict, and the answer has citations."""
    requests = pending(project, capsys)
    request = next(r for r in requests if r["type"] == "judgement" and r["files"])
    name = next(f["file"] for f in request["files"] if (project / f["file"]).read_bytes())
    code, out, err = submit(project, capsys, result(request, "supported", cite(project, name)))
    assert code == 0, err
    assert "added an exact answer" in out
    code, after = judged(project, capsys, "--strict")
    assert request["target"] not in [row["line"] for row in after["open"]]
    answer = next(
        a for a in config.load(project).judgement_answered if request["target"] in a.items
    )
    assert answer.citations[0][0] == name
    assert answer.reason == "The source agrees with the claim."


def test_three_contradicted_results_make_the_request_unknown(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4 and 6: a map change between the results does not reset the count."""
    card, _name, _new = CASES[language(project)]
    for attempt in (1, 2, 3):
        request = of_type(pending(project, capsys), "source_review", card)
        assert request["attempts"] == attempt - 1
        code, out, err = submit(project, capsys, result(request, "contradicted"))
        assert code == 0, err
        change_claim(project, card)
    assert "unknown" in out and of_type_absent(pending(project, capsys), card)
    code, out, _err = run(project, capsys, "decisions", "status", "--json")
    status = json.loads(out)
    assert code == 1 and status["unknown"] == 1
    assert status["unknown_requests"][0]["summary"] == "No."
    code, text, _err = run(project, capsys, "judgement")
    assert f"unknown request source_review:{card}@" in text
    assert "correct" not in text.split("unknown request", 1)[1].split("\n")[0]
    change_source(project, capsys)
    request = of_type(pending(project, capsys), "source_review", card)
    assert request["attempts"] == 0


def test_the_store_identity_of_a_judgement_line_is_its_kind_and_names(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 9 and 6."""
    lines = {
        r["target"]: r["identity"] for r in pending(project, capsys) if r["type"] == "judgement"
    }
    if language(project) == "python":
        line = "single module: Reader contains only pkg.reader"
        assert lines[line] == "single module: Reader pkg.reader"
    else:
        alone = "entry point web (console script) has no sequence (component Application)"
        assert lines[alone] == "entry point: Application"
        same = [line for line in lines if "in acme.web.index has no sequence" in line]
        assert len(same) == 3 and all(lines[line] == line for line in same)


def test_insufficient_evidence_makes_the_request_unknown(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 5 and 6."""
    card, _name, _new = CASES[language(project)]
    request = of_type(pending(project, capsys), "source_review", card)
    code, out, err = submit(project, capsys, result(request, "insufficient_evidence"))
    assert code == 0, err
    assert f"unknown: {request['id']}" in out
    assert of_type_absent(pending(project, capsys), card)
    code, out, _err = run(project, capsys, "decisions", "status")
    assert "1 unknown" in out and f"unknown request {request['id']}" in out
    code, _out, err = submit(project, capsys, result(request, "contradicted"))
    assert code == 1 and "is unknown" in err


def of_type_absent(requests: list[dict[str, Any]], card: str) -> bool:
    return not any(r["type"] == "source_review" and r["target"] == card for r in requests)


def change_claim(root: Path, card: str) -> None:
    """Add a word to the `does` sentence of the component in the model file."""
    model = nest.load(config.load(root)).top.model.component(card)
    assert model is not None
    path = root / "map" / "model.py"
    text = path.read_text(encoding="utf-8")
    assert f'does="{model.does}"' in text
    new = model.does.removesuffix(".") + " again."
    path.write_text(text.replace(f'does="{model.does}"', f'does="{new}"'), encoding="utf-8")


def change_source(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Change the first source file of the component, and write the facts again."""
    _card, name, new = CASES[language(root)]
    path = root / name
    path.write_text(new or path.read_text(encoding="utf-8") + "\nexport const added = 1;\n")
    assert run(root, capsys, "extract")[0] == 0


def test_require_reviews_makes_a_missing_review_a_finding(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 7: the default is false. With true, --strict fails on a missing review."""
    code, out = judged(project, capsys)
    assert out["require_reviews"] is False
    assert out["kinds"]["missing source review"]["open"] == 0
    toml = project / "systemap.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + "\n[judgement]\nrequire_reviews = true\n")
    code, out = judged(project, capsys, "--strict")
    assert code == 1 and out["require_reviews"] is True
    card, _name, _new = CASES[language(project)]
    assert f"missing source review: {card} has no source_review digest." in " ".join(
        row["line"] for row in out["open"]
    )
    # The review request closes the line. The line is not a separate request.
    requests = pending(project, capsys)
    assert not any(r["claim"].startswith("missing source review") for r in requests)


def test_a_component_review_waits_for_a_contradicted_flow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A component review is refused while a flow of the component has a contradicted verdict."""
    write_tree(tmp_path, SOURCE)
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    facts = extract.read_facts(config.load(tmp_path).facts_path)
    refs = tuple(
        f"pkg.{n}@{facts['components'][f'pkg.{n}']['source_sha256']}" for n in ("reader", "writer")
    )
    model = tmp_path / "map" / "model.py"
    text = model.read_text(encoding="utf-8")
    old = 'FLOWS = (Flow("Reader", "Writer", "request", "data"),)'
    model.write_text(
        text.replace(
            old, f'FLOWS = (Flow("Reader", "Writer", "request", "data", source_refs={refs!r}),)'
        )
    )
    capsys.readouterr()
    requests = pending(tmp_path, capsys)
    flow = of_type(requests, "flow_review", "Reader->Writer")
    card = of_type(requests, "source_review", "Reader")
    before = snapshot(tmp_path)
    code, _out, err = submit(
        tmp_path,
        capsys,
        result(flow, "contradicted"),
        result(card, "supported", cite(tmp_path, "pkg/reader.py")),
    )
    assert code == 1 and "Correct the flow first." in err
    assert snapshot(tmp_path) == before
    code, out, err = submit(
        tmp_path, capsys, result(flow, "supported", cite(tmp_path, "pkg/writer.py"))
    )
    assert code == 0, err
    assert "review: flow Reader->Writer" in out
    assert not any(r["type"] == "flow_review" for r in pending(tmp_path, capsys))


def test_stale_facts_are_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The requests need current facts. Changed source gives exit 1 and the action."""
    write_tree(tmp_path, SOURCE)
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    (tmp_path / "pkg/reader.py").write_text("def read(s: str) -> str:\n    return s\n")
    code, _out, err = run(tmp_path, capsys, "decisions", "pending")
    assert code == 1 and "Do systemap refresh." in err


@pytest.mark.parametrize(
    ("name", "cause"),
    [
        ("/etc/hosts", "relative to the repository root"),
        ("C:/x.py", "relative to the repository root"),
        ("//host/share/x.py", "relative to the repository root"),
        ("\\\\host\\share\\x.py", "relative to the repository root"),
        ("pkg\\reader.py", "relative to the repository root"),
        ("pkg/../pkg/reader.py", "without '..'"),
        ("link.py", "outside the repository"),
        ("pkg", "not a regular file"),
        ("pkg/reader.py", ""),
    ],
)
def test_one_function_confines_each_path_to_the_repository(
    tmp_path: Path, name: str, cause: str
) -> None:
    """Each read of a path from the facts, the model, or a verdict goes through `confined`."""
    root = tmp_path / "repo"
    write_tree(root, SOURCE)
    outside = tmp_path / "secret.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    os.symlink(outside, root / "link.py")
    full, found = decisions.confined(root, name)
    assert (full is None) == bool(cause)
    assert cause in found


def test_a_facts_path_out_of_the_repository_is_not_read(tmp_path: Path) -> None:
    """A facts record with a symbolic link out of the repository gives no source file."""
    root = tmp_path / "repo"
    write_tree(root, SOURCE)
    outside = tmp_path / "secret.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    os.symlink(outside, root / "link.py")
    facts = {
        "components": {
            "pkg.reader": {"file": "pkg/reader.py"},
            "pkg.link": {"file": "link.py"},
            "pkg.far": {"file": str(outside)},
        }
    }
    assert decisions.source_files(root, facts) == {"pkg/reader.py": "pkg.reader"}
