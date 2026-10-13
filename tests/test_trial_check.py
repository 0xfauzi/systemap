"""Repairs of the trial results for `check`, `refresh`, `judgement`, `delta`, and `render`.

A trial operated systemap 4ea3bed on click, httpx, ky, and vite. Each test gives a small
fixture for one result (trial-1, trial-11, trial-12, trial-13, trial-14, trial-15). Where
the behavior applies to the two languages, the test gives a Python fixture and a
TypeScript fixture. Each acceptance value is in the docstring of its test.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, sample_model, write_tree

from systemap import (
    answer_migrations,
    check,
    check_actions,
    config,
    delta_report,
    extract,
    journey_coverage,
    judgement,
    source_facts,
    unknown_causes,
)
from systemap.cli import NO_COMPONENTS, main
from systemap.config import Answer
from systemap.delta import Delta, Line

TS_FIXTURE = Path(__file__).parent / "fixtures" / "typescript-app"
LANGUAGES = ("python", "typescript")
LOOP = "run: systemap refresh"


def run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


def mapped_project(root: Path, language: str) -> Path:
    """Write a map that passes `refresh` and `check` in the language."""
    if language == "python":
        write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
        init_two_cards(root, "--no-ci")
    else:
        shutil.copytree(TS_FIXTURE, root, dirs_exist_ok=True)
    assert run(root, "refresh") == 0
    return root


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


# ---- trial-1: a test file that the parser cannot read does not reject the map --------

BAD_TESTS = {
    "python": ("tests/test_broken.py", "def test_x(:\n", "tests/test_bytes.py"),
    "typescript": ("tests/broken.spec.ts", "it('x', () => {\n", "tests/bytes.spec.ts"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_test_file_that_does_not_parse_does_not_reject_the_map(
    tmp_path: Path, language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: in 2 of 2 languages, with one test file that does not parse and one
    test file that is not UTF-8, `refresh` exits 0 and then `check` exits 0. The refresh
    output and the check output give one `unknown surface` line for each of the two files,
    with the file and the reason, and no `source inventory unresolved` line. No output contains
    "run: systemap refresh"."""
    root = mapped_project(tmp_path, language)
    broken, text, unread = BAD_TESTS[language]
    write_tree(root, {broken: text})
    (root / unread).write_bytes(b"\xff\xfe\xfa")
    capsys.readouterr()
    assert run(root, "refresh") == 0
    refreshed = capsys.readouterr().out
    assert run(root, "check") == 0
    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines()]
    assert any(line.startswith(f"test file {broken}:1: ") and "parse" in line for line in lines), (
        out
    )
    assert any(line.startswith(f"test file {unread}:0: source could not be read") for line in lines)
    assert "source inventory unresolved" not in out
    assert LOOP not in refreshed and LOOP not in out
    for name in (broken, unread):
        assert f"  test file {name}:" in refreshed, refreshed


def test_each_cause_that_rejects_the_map_prints_its_line() -> None:
    """Acceptance: for each list field of `check.Result` that makes `ok` false, the report
    contains the text of the line. The test finds the fields from the dataclass, so a
    new rejection field without a report line fails the test."""
    model, _meaning = sample_model()
    base = check.Result([], 0, 0, check.Coverage(True, 1, 1, 0, ()))
    assert base.ok
    found = 0
    for item in dataclasses.fields(check.Result):
        if not isinstance(getattr(base, item.name), list):
            continue
        marker = f"marker line of {item.name}"
        result = dataclasses.replace(base, **{item.name: [marker]})
        if result.ok:
            continue
        found += 1
        report = "\n".join(check.report(model, result))
        assert marker in report, item.name
    assert found >= 6
    rejected = dataclasses.replace(base, coverage=check.Coverage(True, 0, 1, 0, ("cov line",)))
    assert "cov line" in "\n".join(check.report(model, rejected))


BAD_MODULES = {
    "python": ("pkg/broken.py", "def broken(:\n", "pkg.broken"),
    "typescript": ("src/broken.ts", "export function broken( {\n", "acme.web.broken"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_module_that_does_not_parse_gives_its_line_and_no_refresh_loop(
    tmp_path: Path, language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: in 2 of 2 languages, a module that does not parse, with a coverage
    ignore, makes `refresh` and `check` exit 1. Each output contains the group
    `source inventory unresolved: 1 problem` with the line `<module> (<file>)`. No output
    contains "run: systemap refresh". After the refresh, `extract --check` exits 1 and
    does not tell the person to use `extract` again."""
    root = mapped_project(tmp_path, language)
    file, text, module = BAD_MODULES[language]
    write_tree(root, {file: text})
    append(
        root / "systemap.toml",
        f'\n[coverage]\nignore = [{{module = "{module}", reason = "trial fixture"}}]\n',
    )
    capsys.readouterr()
    expected = "source inventory unresolved: 1 problem\n"
    assert run(root, "refresh") == 1
    refreshed = capsys.readouterr().out
    assert run(root, "check") == 1
    out = capsys.readouterr().out
    for text_out in (refreshed, out):
        assert f"\n  {module} ({file})\n" in text_out, text_out
        assert expected in text_out
        assert LOOP not in text_out
    assert run(root, "extract", "--check") == 1
    extracted = capsys.readouterr().out
    assert f"source inventory unresolved: {module} ({file})" in extracted
    assert "run: systemap extract" not in extracted
    assert check_actions.INVENTORY_ACTION in extracted


def test_refresh_does_not_ask_for_a_second_refresh_that_gives_the_same_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: a configured figure that writes over the page makes the page stale
    after each refresh. `refresh` exits 1, and its output does not contain
    "run: systemap refresh". A second `refresh` gives the same exit code and output."""
    root = mapped_project(tmp_path, "python")
    append(root / "systemap.toml", '\n[[figures]]\nout = "index.html"\nmode = "system"\n')
    capsys.readouterr()
    assert run(root, "refresh") == 1
    first = capsys.readouterr().out
    assert run(root, "refresh") == 1
    second = capsys.readouterr().out
    assert LOOP not in first
    assert first.splitlines()[-1] == second.splitlines()[-1]


# ---- trial-11: an entry point group gives its kind in words -------------------------

PUBLIC = {
    "python": {
        "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
        "pkg/__init__.py": "".join(f"def f{k}() -> None:\n    pass\n\n\n" for k in range(5)),
    },
    "typescript": {
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
        "package.json": '{"name":"web"}',
        "tsconfig.json": '{"compilerOptions":{}}',
        "src/index.ts": "".join(f"export function f{k}(): void {{}}\n" for k in range(5)),
    },
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_entry_point_group_gives_its_kind_in_words(tmp_path: Path, language: str) -> None:
    """Acceptance: in 2 of 2 languages, five public functions without a sequence in one
    component give the line "entry point 5 public functions into Api have no sequence
    (component Api)". The line contains no "_"."""
    write_tree(tmp_path, PUBLIC[language])
    facts = extract.build(config.load(tmp_path))
    points = [p for p in facts["entry_points"] if p["kind"] == "public_function"]
    assert len(points) == 5
    owner = {p["module"]: "Api" for p in points}
    lines = journey_coverage._entry_lines(points, owner)
    assert lines == ["entry point 5 public functions into Api have no sequence (component Api)"]


def test_an_answer_with_the_earlier_entry_point_group_line_selects_the_new_line() -> None:
    """Acceptance: an answer item in the earlier form "7 public_functions into" selects
    the line in the new form, with and without a nested-map prefix. Its recorded digest
    stays valid. The warnings name the earlier item. A line in the new form and a line
    of a kind without "_" do not change."""
    earlier = "entry point 7 public_functions into Api have no sequence (component Api)"
    current = "entry point 7 public functions into Api have no sequence (component Api)"
    assert answer_migrations.current_line(earlier) == current
    assert answer_migrations.current_line(f"Sub: {earlier}") == f"Sub: {current}"
    assert answer_migrations.current_line(current) == current
    routes = "entry point 6 routes into Reader have no sequence (component Reader)"
    assert answer_migrations.current_line(routes) == routes
    answer = Answer(items=(earlier,), reason="library", evidence="digest")
    result = judgement.apply_answers([current], [answer], {current: "digest"})
    assert result.open == [] and result.stale == [] and result.pending == []
    assert any(earlier in warning for warning in answer_migrations.warnings([answer]))


# ---- trial-12: the check heading of a model error names the model error ------------


def test_a_meaning_error_is_not_reported_as_a_layout_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: a component without plain words gives the heading
    "map meaning: 1 problem" with the line, and no "map layout: 1 problem" heading. The
    layout heading does not say that the layout has no errors, because the check did not
    render the map. The model is language-neutral, so one fixture is sufficient."""
    root = mapped_project(tmp_path, "python")
    model = root / "map/model.py"
    text = model.read_text(encoding="utf-8")
    start = text.index("PLAIN = {")
    end = text.index("}", start)
    model.write_text(text[:start] + "PLAIN = {" + text[end:], encoding="utf-8")
    capsys.readouterr()
    assert run(root, "check") == 1
    out = capsys.readouterr().out
    assert "map meaning: 2 problems" in out, out
    assert "  Reader has no plain word" in out
    assert "map layout: 2 problems" not in out
    assert "map layout: has no errors" not in out
    assert "small text" not in out.lower()


# ---- trial-13: the fix line of an unknown record follows its cause -----------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_adapters_write_the_cause_of_a_read_or_parse_problem(
    tmp_path: Path, language: str
) -> None:
    """Acceptance: in 2 of 2 languages, a module that does not parse has the cause
    `syntax`, a module that is not UTF-8 has the cause `encoding`, and the same two test
    files have the same two causes."""
    file, text, module = BAD_MODULES[language]
    broken_test, test_text, unread_test = BAD_TESTS[language]
    tree = PUBLIC[language] | {file: text, broken_test: test_text}
    if language == "typescript":
        tree["systemap.toml"] = 'tests_dir = "tests"\n' + tree["systemap.toml"]
        module = "web.broken"
    write_tree(tmp_path, tree)
    latin = "pkg/latin.py" if language == "python" else "src/latin.ts"
    (tmp_path / latin).write_bytes(b"x = '\xe9'\n")
    (tmp_path / unread_test).write_bytes(b"\xff\xfe\xfa")
    facts = extract.build(config.load(tmp_path))
    causes = dict(source_facts.unknown_fact_causes(facts))
    module_lines = [line for line in causes if f"module {module} " in line]
    latin_lines = [line for line in causes if "latin" in line]
    assert module_lines and {causes[line] for line in module_lines} == {unknown_causes.SYNTAX}
    assert latin_lines and {causes[line] for line in latin_lines} == {unknown_causes.ENCODING}
    test_causes = {issue["file"]: issue["problem"]["cause"] for issue in facts["test_file_issues"]}
    assert test_causes == {broken_test: unknown_causes.SYNTAX, unread_test: unknown_causes.ENCODING}


def test_the_typescript_adapter_writes_the_cause_of_a_bin_and_a_configuration_package(
    tmp_path: Path,
) -> None:
    """Acceptance: a package bin that is a .js file has the cause `target`, and a missing
    package in `extends` has the cause `package`. These two records come only from the
    TypeScript adapter."""
    write_tree(
        tmp_path,
        {
            **PUBLIC["typescript"],
            "package.json": '{"name":"web","bin":{"web":"bin/web.js"}}',
            "bin/web.js": "#!/usr/bin/env node\nimport('../dist/index.js')\n",
            "tsconfig.json": '{"extends":"@missing/tsconfig","compilerOptions":{}}',
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert [issue["cause"] for issue in facts["entry_point_issues"]] == [unknown_causes.TARGET]
    assert [issue["cause"] for issue in facts["config_issues"]] == [unknown_causes.PACKAGE]


def test_the_check_gives_one_fix_line_for_each_cause(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: a missing package in `extends` gives the fix line of the cause
    `package` and not the fix line of a parse error. The earlier text "Add parser
    support" for all causes does not occur."""
    root = mapped_project(tmp_path, "typescript")
    tsconfig = root / "tsconfig.json"
    tsconfig.write_text(
        tsconfig.read_text(encoding="utf-8").replace("{", '{"extends":"@missing/tsconfig",', 1),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert run(root, "refresh") == 0
    assert run(root, "check") == 0
    out = capsys.readouterr().out
    assert f"  fix: {unknown_causes.FIX[unknown_causes.PACKAGE]}" in out
    assert unknown_causes.FIX[unknown_causes.SYNTAX] not in out
    assert "Add parser support" not in out


def test_each_cause_has_one_fix_text_and_an_older_record_has_the_not_known_text() -> None:
    """Acceptance: each cause has a different fix text. A record without `cause` has the
    cause "not known" and gets the fix text of that value, not the text of a different
    cause."""
    texts = [unknown_causes.FIX[cause] for cause in unknown_causes.CAUSES]
    assert len(set(texts)) == len(texts) == len(unknown_causes.CAUSES)
    facts = {"config_issues": [{"file": "tsconfig.json", "reference": "@x/y"}]}
    assert [cause for _line, cause in source_facts.unknown_fact_causes(facts)] == [
        unknown_causes.NOT_KNOWN
    ]
    lines = unknown_causes.fix_lines([unknown_causes.NOT_KNOWN])
    assert lines == [f"  fix: {unknown_causes.FIX[unknown_causes.NOT_KNOWN]}"]


# ---- trial-14: the delta header tells what it counts ------------------------------


def test_the_delta_header_says_that_it_counts_the_components_with_changes() -> None:
    """Acceptance: a delta with lines that name 2 of 7 components ends its count text with
    "2 of 7 components have changes". The text "specified" does not occur."""
    lines = (
        Line(kind="added", text="a", cards=("Api",)),
        Line(kind="removed", text="b", cards=("Api", "Store")),
    )
    d = Delta("a" * 40, "b" * 40, "main", "HEAD", 1, 1, 1, 0, 7, lines)
    text = delta_report._counts(d)
    assert text.endswith("2 of 7 components have changes")
    assert "specified" not in text


# ---- trial-15: the empty model and a command that cannot operate -------------------

EMPTY = {
    "python": {"pkg/__init__.py": "", "pkg/app.py": "def run() -> None:\n    pass\n"},
    "typescript": {
        "package.json": '{"name":"web"}',
        "tsconfig.json": '{"compilerOptions":{}}',
        "src/index.ts": "export function run(): void {}\n",
    },
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_empty_model_gives_the_same_exit_code_in_check_and_strict_judgement(
    tmp_path: Path, language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: in 2 of 2 languages, with the starter model, `check`, `judgement
    --strict`, and `judgement --json --strict` exit 1, and each gives the line that the
    model has no components. `judgement` without `--strict` exits 0."""
    write_tree(tmp_path, EMPTY[language])
    assert run(tmp_path, "init", "--no-ci") == 0
    capsys.readouterr()
    assert run(tmp_path, "check") == 1
    assert NO_COMPONENTS in capsys.readouterr().out
    assert run(tmp_path, "judgement", "--strict") == 1
    assert NO_COMPONENTS in capsys.readouterr().out
    assert run(tmp_path, "judgement", "--json", "--strict") == 1
    captured = capsys.readouterr()
    assert NO_COMPONENTS in captured.err
    assert json.loads(captured.out)["open"] == []
    assert run(tmp_path, "judgement") == 0


NO_ROOTS = {
    "python": {"lib/app.py": "def run() -> None:\n    pass\n", "systemap.toml": ""},
    "typescript": {
        "systemap.toml": 'language = "typescript"\n',
        "package.json": '{"name":"web"}',
        "lib/app.ts": "export function run(): void {}\n",
    },
}


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("command", ["render", "facts", "figure"])
def test_a_command_without_facts_does_not_name_an_extract_that_fails(
    tmp_path: Path, language: str, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: in 2 of 2 languages, without package roots and without facts, `extract`
    exits 2. `render`, `facts`, and `figure` also exit 2 with the same package-root text,
    and their output does not contain "run: systemap extract"."""
    write_tree(tmp_path, NO_ROOTS[language])
    assert run(tmp_path, "init", "--no-ci") == 0
    assert run(tmp_path, "extract") == 2
    extract_err = capsys.readouterr().err
    assert "package roots" in extract_err
    assert run(tmp_path, command) == 2
    captured = capsys.readouterr()
    assert "run: systemap extract" not in captured.out + captured.err
    assert captured.err == extract_err
