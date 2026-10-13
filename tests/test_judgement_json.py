"""`systemap judgement --json`: the judgement report as one JSON object for programs.

Acceptance values:

1. For a fixture map with known open lines, the JSON `open` list contains exactly
   the lines that the text output gives, with the same identifiers and in the same order.
2. The `evidence` value of an open line equals the digest that an exact answer must
   have. Proof: write that answer, operate `judgement` again, and the line closes.
3. The exit codes of `--json` equal the exit codes of the text mode, with and without
   `--strict`, for a map with open lines and for a map with no open line.
4. The JSON output contains no explanation text, and `--brief` does not change it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import explain, judgement, judgement_json
from systemap.cli import main
from systemap.config import Answer

SOURCE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "from pkg.reader import read\n\n\ndef write(request: str) -> str:\n    return read(request)\n",
}
READER = "single module: Reader contains only pkg.reader"
WRITER = "single module: Writer contains only pkg.writer"
THIN = "thin layer: control shows 0 components"


@pytest.fixture
def mapped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """The two-card starter with facts. It has four open lines and no answer."""
    write_tree(tmp_path, SOURCE)
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    return tmp_path


@pytest.fixture(params=["python", "typescript"])
def project(
    request: pytest.FixtureRequest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> Path:
    """A mapped Python project or a mapped TypeScript project, each with open lines."""
    if request.param == "python":
        write_tree(tmp_path, SOURCE)
        init_two_cards(tmp_path, "--no-ci")
        assert main(["--root", str(tmp_path), "extract"]) == 0
    else:
        fixture = Path(__file__).parent / "fixtures" / "typescript-app"
        shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
        assert main(["--root", str(tmp_path), "refresh"]) == 0
    capsys.readouterr()
    return tmp_path


def answer(root: Path, *rows: str) -> None:
    """Replace the [judgement] answered table with these rows."""
    toml = root / "systemap.toml"
    text = toml.read_text(encoding="utf-8").split("\n[judgement]\n")[0]
    toml.write_text(
        text + "\n[judgement]\nanswered = [\n" + "".join(f"    {r},\n" for r in rows) + "]\n",
        encoding="utf-8",
    )


def exact(line: str, digest: str) -> str:
    return f"{{ item = {json.dumps(line)}, evidence = {json.dumps(digest)}, reason = 'a test' }}"


def as_json(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, Any]:
    code = main(["--root", str(root), "judgement", "--json", *argv])
    return code, json.loads(capsys.readouterr().out)


def text_open_lines(root: Path, capsys: pytest.CaptureFixture[str]) -> list[str]:
    """The open lines of the text report, without the two-space indent."""
    assert main(["--root", str(root), "judgement", "--brief"]) == 0
    rows = capsys.readouterr().out.splitlines()
    notices = ("stale answer: ", "pending answer: ", "policy answer: ")
    return [
        row[2:]
        for row in rows
        if row.startswith("  ") and not row.startswith("   ") and not row[2:].startswith(notices)
    ]


def test_open_lines_equal_the_text_report_for_each_language(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1 for a Python fixture and a TypeScript fixture, without answers."""
    text = text_open_lines(project, capsys)
    code, out = as_json(project, capsys)
    assert code == 0 and text
    assert [row["line"] for row in out["open"]] == text
    assert all(row["kind"] for row in out["open"])


def test_open_lines_equal_the_text_report(mapped: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Acceptance 1, with a pending answer, a stale answer, and a policy answer."""
    answer(
        mapped,
        exact(READER, "0" * 64),
        exact("single module: Gone contains only pkg.gone", "0" * 64),
        "{ kind = 'thin layer', policy = true, reason = 'a test' }",
    )
    text = text_open_lines(mapped, capsys)
    code, out = as_json(mapped, capsys)
    assert code == 0
    assert [row["line"] for row in out["open"]] == text
    assert READER in text and WRITER in text and THIN not in text
    assert out["schema_version"] == 1
    assert {row["line"]: row["kind"] for row in out["open"]}[READER] == "single module"
    assert out["stale_answers"] == ["single module: Gone contains only pkg.gone"]
    assert out["answered"] == {
        "count": 1,
        "answers": [
            {"answer": 'kind = "thin layer"', "items": [], "reason": "a test", "lines": [THIN]}
        ],
    }
    assert out["source_reviews"] == {"current": 0, "stale": 0, "missing": 2}
    assert out["kinds"]["single module"] == {"open": 2, "answered": 0}
    assert out["kinds"]["thin layer"] == {"open": 0, "answered": 1}
    assert sum(k["open"] for k in out["kinds"].values()) == len(text)


def test_the_digest_closes_the_line(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Acceptance 2: an exact answer with the JSON digest closes each open line."""
    _code, before = as_json(project, capsys)
    assert before["open"]
    assert all(len(row["evidence"]) == 64 for row in before["open"])
    answer(project, *(exact(row["line"], row["evidence"]) for row in before["open"]))
    code, after = as_json(project, capsys, "--strict")
    assert code == 0
    assert after["open"] == []
    assert after["answered"]["count"] == len(before["open"])
    assert [a["lines"] for a in after["answered"]["answers"]] == [
        [row["line"]] for row in before["open"]
    ]


@pytest.mark.parametrize("strict", [False, True])
def test_exit_codes_equal_the_text_mode(
    project: Path, capsys: pytest.CaptureFixture[str], strict: bool
) -> None:
    """Acceptance 3: the exit codes agree with open lines and with no open line."""
    flag = ["--strict"] if strict else []
    text_code = main(["--root", str(project), "judgement", *flag])
    capsys.readouterr()
    code, before = as_json(project, capsys, *flag)
    assert (text_code, code) == ((1, 1) if strict else (0, 0))
    answer(project, *(exact(row["line"], row["evidence"]) for row in before["open"]))
    text_code = main(["--root", str(project), "judgement", *flag])
    capsys.readouterr()
    code, _after = as_json(project, capsys, *flag)
    assert (text_code, code) == (0, 0)


def test_no_explanation_and_brief_has_no_effect(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4: the object has no explanation row, with or without --brief."""
    main(["--root", str(mapped), "judgement", "--json"])
    full = capsys.readouterr().out
    main(["--root", str(mapped), "judgement", "--json", "--brief"])
    assert capsys.readouterr().out == full
    for kind in ("single module", "thin layer", "flow review"):
        for row in explain.rows(kind):
            assert row.strip() not in full


def test_without_facts_the_output_is_still_one_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without facts, the notice goes to stderr and stdout stays one JSON object."""
    write_tree(tmp_path, SOURCE)
    init_two_cards(tmp_path, "--no-ci")
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "judgement", "--json"]) == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert "No facts are available" in captured.err
    assert out["source_reviews"] is None
    assert READER in [row["line"] for row in out["open"]]


def test_a_model_without_components_gives_an_empty_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The starter model has no components. With `--strict`, the exit code is 1, as in the
    text mode and in `check` (trial-15)."""
    write_tree(tmp_path, SOURCE)
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "judgement", "--json", "--strict"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == judgement_json.empty()
    assert judgement_json.empty()["open"] == []
    assert "The model has no components" in captured.err


def test_kind_limits_the_open_list_only(mapped: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--kind selects the open rows. The counts include all kinds, as in the text mode."""
    _code, out = as_json(mapped, capsys, "--kind", "thin layer")
    assert [row["line"] for row in out["open"]] == [THIN]
    assert out["kinds"]["single module"]["open"] == 2


def test_crossing_detail_is_in_each_row() -> None:
    """A crossing-import row gives its imports. Other rows give an empty list."""
    line = "crossing import: A imports B in 1 module and no flow connects them"
    lines = [line, READER]
    judged = judgement_json.Judged(
        lines=lines,
        evidence={line: "a" * 64},
        result=judgement.apply_answers(lines, [Answer((READER,), "r")]),
    )
    out = judgement_json.payload(judged, {line: ["pkg.a imports pkg.b"]}, None)
    assert out["open"] == [
        {
            "line": line,
            "kind": "crossing import",
            "detail": ["pkg.a imports pkg.b"],
            "evidence": "a" * 64,
        }
    ]
    assert out["answered"]["answers"] == [
        {"answer": READER, "items": [READER], "reason": "r", "lines": [READER]}
    ]
    assert out["source_reviews"] is None
