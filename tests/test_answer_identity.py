"""A recorded answer stays applicable until a fact that its finding cites changes.

Issues 90 and 114. Acceptance values, each for a Python fixture and a TypeScript fixture:

1. A comment in the source of a cited module does not change the evidence of a
   `single module`, a `crossing import`, or an `entry point` line. A change to a function
   body does not change the evidence of a `single module` line.
2. A new public name or a new import in a cited module changes the evidence of a
   `single module` line. A new entry point changes the evidence of an `entry point` line.
3. A line about behavior keeps the source in its evidence: a comment changes the
   evidence of a `flow review` line.
4. A new test of a cited module does not change the evidence of a line.
5. An import that a different component adds or removes does not change the evidence of
   an `entry point` line (`docs/reference.md`: a change to a different component does not
   open the finding again).
6. A `crossing import` line contains no count. The text report gives the count in the
   row `count: N module(s)` below the line, and `judgement --json` gives it in
   `open[].count`. A `package_export` line contains no count. Its record has `count`, and
   the row below the line is `count: N targets`.
7. `judgement` gives no line about a test file. An answer for such a line is stale, and
   the report tells that the line is no longer a finding.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree
from test_answer_evidence import FIXTURE, SERVICE, SOURCE

from systemap import config, extract, judgement, nest
from systemap.cli import main

SCRIPT = '[project]\nname = "pkg"\nversion = "0"\n[project.scripts]\nread = "pkg.reader:read"\n'
# Each language: the named component, its module, its file, the other component, the
# file of the other component, and the component of the entry point line.
CASES: dict[str, dict[str, str]] = {
    "python": {
        "card": "Reader",
        "module": "pkg.reader",
        "file": "pkg/reader.py",
        "other": "Writer",
        "other_file": "pkg/writer.py",
        "entry_card": "Reader",
        "entry_file": "pkg/reader.py",
        "comment": "\n# A comment that changes no fact.\n",
        "body": ("return source\n", "return source.strip()\n"),
        "name": "\n\ndef added() -> None:\n    pass\n",
        "test": "tests/test_added.py",
        "test_text": "from pkg.reader import read\n\n\ndef test_read() -> None:\n    read('a')\n",
        "broken_test": "tests/test_broken.py",
        "broken_text": "def test_x(:\n",
    },
    "typescript": {
        "card": "Service",
        "module": "acme.web.service",
        "file": "src/service.ts",
        "other": "Application",
        "other_file": "src/index.ts",
        "entry_card": "Application",
        "entry_file": "src/cli.ts",
        "comment": "\n// A comment that changes no fact.\n",
        "body": (
            "return fetchUser(z.string().parse(id));",
            "return fetchUser(z.string().parse(id.trim()));",
        ),
        "name": "\nexport const added = 1;\n",
        "test": "tests/added.spec.ts",
        "test_text": 'import { serve } from "@/service";\n\ntest("serves", () => serve("2"));\n',
        "broken_test": "tests/broken.spec.ts",
        "broken_text": "it('x', () => {\n",
    },
}


@pytest.fixture(params=["python", "typescript"])
def project(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A mapped project with a `single module`, a `crossing import`, and an
    `entry point` line."""
    if request.param == "python":
        write_tree(tmp_path, {**SOURCE, "pyproject.toml": SCRIPT})
        init_two_cards(tmp_path, "--no-ci")
        flows = 'FLOWS = (Flow("Reader", "Writer", "request", "data"),)'
        replace(tmp_path, "map/model.py", flows, "FLOWS = ()")
    else:
        shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
        replace(tmp_path, "map/model.py", '            "acme.web.service",\n', "")
        replace(tmp_path, "map/model.py", "COMPONENTS = (\n", "COMPONENTS = (\n" + SERVICE)
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def case(root: Path) -> dict[str, str]:
    return CASES[config.load(root).language]


def replace(root: Path, name: str, old: str, new: str) -> None:
    path = root / name
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append(root: Path, name: str, text: str) -> None:
    path = root / name
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def lines_of(root: Path) -> list[str]:
    cfg = config.load(root)
    return judgement.run_tree(nest.load(cfg), extract.build(cfg))


def line_of(root: Path, start: str) -> str:
    found = [line for line in lines_of(root) if line.startswith(start)]
    assert len(found) == 1, (start, lines_of(root))
    return found[0]


def evidence(root: Path, line: str) -> str:
    cfg = config.load(root)
    return judgement.evidence_for_tree(nest.load(cfg), extract.build(cfg), root, [line])[line]


def structural_lines(root: Path) -> list[str]:
    """The `single module`, `crossing import`, and `entry point` lines of the case."""
    c = case(root)
    return [
        line_of(root, f"single module: {c['card']} contains only "),
        line_of(root, f"crossing import: {c['card']} imports ")
        if c["card"] == "Service"
        else line_of(root, f"crossing import: {c['other']} imports {c['card']}"),
        next(
            line
            for line in lines_of(root)
            if line.startswith("entry point ") and f"(component {c['entry_card']})" in line
        ),
    ]


def test_a_comment_keeps_the_evidence_of_structural_lines(project: Path) -> None:
    """Acceptance 1."""
    c = case(project)
    lines = structural_lines(project)
    before = [evidence(project, line) for line in lines]
    for name in {c["file"], c["other_file"], c["entry_file"]}:
        append(project, name, c["comment"])
    assert [evidence(project, line) for line in lines] == before


def test_a_function_body_keeps_the_evidence_of_a_single_module_line(project: Path) -> None:
    """Acceptance 1."""
    c = case(project)
    line = structural_lines(project)[0]
    before = evidence(project, line)
    replace(project, c["file"], *c["body"])
    assert evidence(project, line) == before


def test_a_new_name_changes_the_evidence_of_a_single_module_line(project: Path) -> None:
    """Acceptance 2."""
    c = case(project)
    line = structural_lines(project)[0]
    before = evidence(project, line)
    append(project, c["file"], c["name"])
    assert evidence(project, line) != before


def test_a_comment_changes_the_evidence_of_a_flow_review_line(project: Path) -> None:
    """Acceptance 3: a flow claim is about behavior, so its evidence keeps the source."""
    c = case(project)
    line = (
        f"flow review: {c['other']}->{c['card']} (request) has structural evidence but no "
        "source review. Give source references for direction and artifact, or change the flow."
    )
    before = evidence(project, line)
    append(project, c["file"], c["comment"])
    assert evidence(project, line) != before


def test_a_new_test_keeps_the_evidence(project: Path) -> None:
    """Acceptance 4."""
    c = case(project)
    lines = structural_lines(project)
    before = [evidence(project, line) for line in lines]
    cfg = config.load(project)
    tests_before = extract.build(cfg)["components"][c["module"]]["tests_digest"]
    write_tree(project, {c["test"]: c["test_text"]})
    assert extract.build(cfg)["components"][c["module"]]["tests_digest"] != tests_before
    assert [evidence(project, line) for line in lines] == before


def test_an_import_in_a_different_component_keeps_the_entry_point_evidence(
    project: Path,
) -> None:
    """Acceptance 5. Python: the Writer module stops to import the Reader module. TypeScript:
    the Service module also imports a module of Application. Each change gives a new
    `imported_by` value to a module of the entry point component."""
    c = case(project)
    line = structural_lines(project)[2]
    before = evidence(project, line)
    if c["card"] == "Reader":
        write_tree(
            project, {"pkg/writer.py": "def write(request: str) -> str:\n    return request\n"}
        )
    else:
        replace(
            project,
            c["file"],
            'import { z } from "zod";',
            'import { z } from "zod";\nimport { UserView } from "@/view";',
        )
        append(project, c["file"], "\nexport const view = UserView;\n")
    assert evidence(project, line) == before


def test_a_new_entry_point_changes_the_entry_point_evidence(project: Path) -> None:
    """Acceptance 2: the entry point records of the cited modules are cited facts."""
    c = case(project)
    line = structural_lines(project)[2]
    before = evidence(project, line)
    if c["card"] == "Reader":
        replace(
            project,
            "pyproject.toml",
            'read = "pkg.reader:read"',
            'read = "pkg.reader:read"\nalso = "pkg.reader:read"',
        )
    else:
        replace(
            project,
            "package.json",
            '"web": "src/cli.ts"',
            '"web": "src/cli.ts", "also": "src/cli.ts"',
        )
    assert evidence(project, line) != before


def judgement_json(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    capsys.readouterr()
    main(["--root", str(root), "judgement", "--json"])
    data: dict[str, Any] = json.loads(capsys.readouterr().out)
    return data


def test_the_crossing_count_is_in_a_row_below_the_line(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6."""
    line = structural_lines(project)[1]
    assert " in 1 module" not in line
    assert line.endswith(" and no flow connects them")
    capsys.readouterr()
    main(["--root", str(project), "judgement"])
    out = capsys.readouterr().out.splitlines()
    assert out[out.index(f"  {line}") + 1] == "    count: 1 module"
    row = next(row for row in judgement_json(project, capsys)["open"] if row["line"] == line)
    assert row["count"] == 1


def test_the_package_export_count_is_in_a_row_below_the_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6. Only the TypeScript adapter writes `package_export` records."""
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    exports = '"exports": {"./a": "./dist/a.js", "./b": "./dist/b.js", "./c": "./dist/c.js"},'
    replace(tmp_path, "package.json", '"bin": {', exports + '\n  "bin": {')
    assert main(["--root", str(tmp_path), "extract"]) == 0
    [issue] = extract.build(config.load(tmp_path))["entry_point_issues"]
    assert issue["target"] == "dist/a.js"
    assert issue["count"] == 3
    line = line_of(tmp_path, "unknown surface: package_export ")
    assert line == (
        "unknown surface: package_export @acme/web -> dist/a.js: "
        "The package.json export targets have no resolved TypeScript modules."
    )
    capsys.readouterr()
    main(["--root", str(tmp_path), "judgement"])
    out = capsys.readouterr().out.splitlines()
    assert "    count: 3 targets" in out[out.index(f"  {line}") + 1 :][:3]
    row = next(row for row in judgement_json(tmp_path, capsys)["open"] if row["line"] == line)
    assert row["count"] == 3


def test_judgement_gives_no_line_about_a_test_file(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 7."""
    c = case(project)
    write_tree(project, {c["broken_test"]: c["broken_text"]})
    assert main(["--root", str(project), "extract"]) == 0
    facts = extract.build(config.load(project))
    assert [issue["file"] for issue in facts["test_file_issues"]] == [c["broken_test"]]
    assert not [line for line in lines_of(project) if "test file" in line]
    item = f"unknown surface: test file {c['broken_test']}: source could not be parsed"
    with (project / "systemap.toml").open("a", encoding="utf-8") as handle:
        handle.write(
            f'\n[judgement]\nanswered = [{{ item = "{item}", reason = "A test.", '
            f'evidence = "{"0" * 64}" }}]\n'
        )
    capsys.readouterr()
    assert main(["--root", str(project), "judgement"]) == 0
    out = capsys.readouterr().out
    assert f"stale answer: '{item}' is no longer a finding" in out
