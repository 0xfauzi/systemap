"""Repairs of the third trial results (trial3-1 to trial3-8).

A third trial operated systemap 0a51437 on ky and vite. Each test gives a small fixture
that copies the layout of one result. No test clones a repository. Each acceptance value
is in the docstring of its test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_trial_check import SOURCES, UNREAD, mapped_project
from test_trial_python import _dated_repo

from systemap import (
    answer_migrations,
    answer_write,
    check,
    config,
    extract,
    facts_file,
    history,
    judgement,
    judgement_evidence,
    source_facts,
    unknown_causes,
)
from systemap.cli import main
from systemap.config import Answer
from systemap.model import Component

# ---- trial3-1: an answer stays valid when the line of its statement moves -------------

# A line above the statement, and a different statement at the same place. The first
# line of the file stays above the statement, because a parse error line can show the
# line before the statement.
COMMENT = {"python": "# A comment.\n", "typescript": "// A comment.\n"}
FIRST = {"python": "LIMIT = 3\n", "typescript": "export const LIMIT = 3;\n"}
CHANGED = {
    "python": "def read(source: int -> str:\n    return source\n",
    "typescript": "export function serve(id: number {\n",
}


def _judge(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    capsys.readouterr()
    main(["--root", str(root), "judgement", "--json"])
    found: dict[str, Any] = json.loads(capsys.readouterr().out)
    return found


def _located(out: dict[str, Any], module: str) -> list[dict[str, Any]]:
    head = f"unknown surface: module {module} ("
    return [row for row in out["open"] if row["line"].startswith(head)]


def _answer_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"item": row["line"], "reason": "Known.", "evidence": row["evidence"]} for row in rows]


def _answered_lines(out: dict[str, Any]) -> list[str]:
    return [line for answer in out["answered"]["answers"] for line in answer["lines"]]


def _sources(root: Path, line: str) -> list[int]:
    """Give the source line of each record of an `unknown surface` line."""
    facts = facts_file.read_facts(config.load(root).facts_path, root)
    return [found.line for found in source_facts.located_records(facts)[line]]


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_an_answer_stays_valid_when_a_line_moves_above_its_statement(
    tmp_path: Path, language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial3-1. Acceptance: in 2 of 2 languages, a module that does not parse gives an
    `unknown surface` line with the location `(<file>)`, without a line number, excerpt,
    or parser version. The `sources` field of its `judgement --json` row gives the line 2.
    An exact answer with the evidence digest from `judgement --json` answers the line.
    After one comment line at the top of the file, the record has the line 3, the line
    text does not change, and the same answer answers it: the line is not open, and the
    report has no stale answer. After a change to the statement, the answer does not
    answer the line: the line is open, because the evidence changed.

    On 0a51437, after the comment line, the answer was stale and the line was open
    again, because the line number is part of the line and the evidence has the digest
    of the full source file."""
    file, module, _card = UNREAD[language]
    root = mapped_project(tmp_path, language)
    write_tree(root, {file: FIRST[language] + SOURCES[(language, "syntax error")]})
    assert main(["--root", str(root), "refresh"]) == 0
    rows = _located(_judge(root, capsys), module)
    assert len(rows) == 1
    assert rows[0]["line"].startswith(f"unknown surface: module {module} ({file}): ")
    assert "version" not in rows[0]["line"] and "excerpt" not in rows[0]["line"]
    assert [source["line"] for source in rows[0]["sources"]] == [2]
    answer_write.add(root, config.CONFIG_FILE, _answer_rows(rows))
    out = _judge(root, capsys)
    assert _located(out, module) == [] and out["stale_answers"] == []
    first = COMMENT[language] + FIRST[language]
    write_tree(root, {file: first + SOURCES[(language, "syntax error")]})
    assert main(["--root", str(root), "refresh"]) == 0
    out = _judge(root, capsys)
    assert _located(out, module) == [] and out["stale_answers"] == []
    assert rows[0]["line"] in _answered_lines(out)
    assert _sources(root, rows[0]["line"]) == [3]
    write_tree(root, {file: first + CHANGED[language]})
    assert main(["--root", str(root), "refresh"]) == 0
    assert _located(_judge(root, capsys), module)


# The vite layout of trial3-1: a type re-export of a declaration file in a claimed module.
DECLARED_TYPES = {
    "package.json": json.dumps(
        {
            "name": "@acme/web",
            "bin": {"web": "src/cli.ts"},
            "imports": {"#types/*": "./types/*.d.ts"},
        }
    ),
    "types/payload.d.ts": "export type Payload = string;\n",
}
SERVICE = "src/service.ts"
REEXPORT = "export type { Payload } from '#types/payload';\n"


def test_an_answer_for_a_declaration_file_line_stays_valid_when_the_line_moves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial3-1, the vite case. Acceptance: a type re-export of a declaration file gives
    one line without a line number. The text report gives the rows `cause: declaration
    file`, `at: src/service.ts:<n>`, and `excerpt: '<statement>'` below it. An exact answer
    answers it. After a comment line at the top of the file, the record has the line
    `<n + 1>`, and the answer still answers the same line, with no stale answer. After a
    change to the names of the statement, the line is open, and the answer is stale."""
    root = mapped_project(tmp_path, "typescript")
    service = (root / SERVICE).read_text(encoding="utf-8")
    write_tree(root, {**DECLARED_TYPES, SERVICE: service + REEXPORT})
    assert main(["--root", str(root), "refresh"]) == 0
    rows = _located(_judge(root, capsys), "acme.web.service")
    assert [row["cause"] for row in rows] == [unknown_causes.DECLARATION_FILE]
    first = service.count("\n") + 1
    assert f"({SERVICE}): " in rows[0]["line"]
    capsys.readouterr()
    main(["--root", str(root), "judgement"])
    text = capsys.readouterr().out.splitlines()
    at = text.index(f"  {rows[0]['line']}")
    assert text[at + 1 : at + 4] == [
        "    cause: declaration file",
        f"    at: {SERVICE}:{first}",
        f"    excerpt: {REEXPORT.strip()!r}",
    ]
    answer_write.add(root, config.CONFIG_FILE, _answer_rows(rows))
    write_tree(root, {SERVICE: "// A comment.\n" + service + REEXPORT})
    assert main(["--root", str(root), "refresh"]) == 0
    out = _judge(root, capsys)
    assert _located(out, "acme.web.service") == [] and out["stale_answers"] == []
    assert rows[0]["line"] in _answered_lines(out)
    assert _sources(root, rows[0]["line"]) == [first + 1]
    other = REEXPORT.replace("{ Payload }", "{ Payload as Other }")
    write_tree(root, {SERVICE: "// A comment.\n" + service + other})
    assert main(["--root", str(root), "refresh"]) == 0
    out = _judge(root, capsys)
    assert _located(out, "acme.web.service") and out["stale_answers"] == [rows[0]["line"]]


def _rows_below(out: str, line: str) -> list[str]:
    """Give the indented rows below one line of a `check` or `refresh` report."""
    rows = out.splitlines()
    at = rows.index(f"  {line.removeprefix('unknown surface: ')}")
    below = []
    for row in rows[at + 1 :]:
        if not row.startswith("    "):
            break
        below.append(row.strip())
    return below


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_check_and_refresh_give_the_source_rows_below_a_short_line(
    tmp_path: Path, language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial3-1 follow-up. Acceptance: in 2 of 2 languages, `check` and `refresh` give
    the same source rows below each short `unknown surface` line as `judgement`, from
    the one function `source_facts.source_rows`:

    - A module parse record gives `at: <file>:1` and `parser version: <version>`. The
      TypeScript record also gives `excerpt:`, because only that adapter writes it.
    - Python: a test file parse record gives `at: tests/test_broken.py:1` and
      `excerpt: 'def test_x(:'`. The Python adapter writes no re-export target record
      with a line, so the second record of Python is this test file record.
    - TypeScript: a re-export target record gives `at: src/index.ts:4` and the statement
      as `excerpt:`.

    Before this repair, `check` gave the short line with no row, so the location was
    missing."""
    file, module, _card = UNREAD[language]
    root = mapped_project(tmp_path, language)
    write_tree(root, {file: SOURCES[(language, "syntax error")]})
    if language == "python":
        write_tree(root, {"tests/test_broken.py": "def test_x(:\n"})
        second = "unknown surface: test file tests/test_broken.py: "
        second_rows = ["at: tests/test_broken.py:1", "excerpt: 'def test_x(:'"]
    else:
        index = (root / "src/index.ts").read_text(encoding="utf-8")
        write_tree(root, {**DECLARED_TYPES, "src/index.ts": index + REEXPORT})
        second = "unknown surface: module acme.web.index (src/index.ts): the re-export target"
        second_rows = ["at: src/index.ts:4", f"excerpt: {REEXPORT.strip()!r}"]
    capsys.readouterr()
    assert main(["--root", str(root), "refresh"]) == 0
    refreshed = capsys.readouterr().out
    assert main(["--root", str(root), "check"]) == 0
    checked = capsys.readouterr().out
    lines = source_facts.unknown_fact_lines(
        facts_file.read_facts(config.load(root).facts_path, root)
    )
    [parse] = [line for line in lines if line.startswith(f"unknown surface: module {module} (")]
    [other] = [line for line in lines if line.startswith(second)]
    for out in (refreshed, checked):
        parse_rows = _rows_below(out, parse)
        assert parse_rows[0] == f"at: {file}:1"
        assert parse_rows[-1].startswith("parser version: ")
        if language == "typescript":
            assert parse_rows[1].startswith("excerpt: ") and len(parse_rows) == 3
        else:
            assert parse_rows[-1] == f"parser version: {sys.version.split()[0]}"
            assert len(parse_rows) == 2
        assert _rows_below(out, other) == second_rows


def test_two_records_with_the_same_line_give_one_line_and_two_sources(tmp_path: Path) -> None:
    """trial3-1. Acceptance: two statements in one module that give the same line text
    give one line, with two sources (the lines 1 and 3). The evidence of the line does not
    change when a line is added above the two statements. It changes when one of the two
    statements changes."""
    files = {
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
        "package.json": json.dumps({"name": "web", "imports": {"#types/*": "./types/*.d.ts"}}),
        "tsconfig.json": "{}",
        "types/t.d.ts": "export type T = string;\n",
    }
    one = "export type { T } from '#types/t'\nexport const a = 1\n"
    two = one + "export type { T } from '#types/t'\n"
    found = []
    for index in (one, two, "// A.\n" + two, two.replace("'\n", "';\n", 1)):
        write_tree(tmp_path, {**files, "src/index.ts": index})
        located = source_facts.located_records(extract.build(config.load(tmp_path)))
        [line] = [line for line in located if "module web.index" in line]
        state = judgement_evidence.located_state(tmp_path, located[line])
        found.append((line, [item.line for item in located[line]], json.dumps(state)))
    assert [lines for _line, lines, _state in found] == [[1], [1, 3], [2, 4], [1, 3]]
    assert len({line for line, _lines, _state in found}) == 1
    assert found[1][2] == found[2][2] != found[3][2]


# Each earlier form with a volatile value, and its current form (facts format 11).
EARLIER_FORMS = [
    (
        "unknown surface: module web.index (src/index.ts:8): the re-export target "
        "'#types/missing' is outside the extracted module set. Names: Missing.",
        "unknown surface: module web.index (src/index.ts): the re-export target "
        "'#types/missing' is outside the extracted module set. Names: Missing.",
    ),
    (
        "unknown surface: test file tests/a.spec.ts:3: The parser could not parse the source "
        "syntax. Source excerpt: 'it(' (parser version tree-sitter 0.25.2, "
        "tree-sitter-typescript 0.23.2)",
        "unknown surface: test file tests/a.spec.ts: The parser could not parse the source syntax.",
    ),
    (
        "unknown surface: test file tests/test_a.py:0: source could not be read: encoding",
        "unknown surface: test file tests/test_a.py: source could not be read: encoding",
    ),
    (
        "unknown surface: module app.broken (app/broken.py:3): source could not be parsed: "
        "SyntaxError (parser version 3.11.10)",
        "unknown surface: module app.broken (app/broken.py): source could not be parsed: "
        "SyntaxError",
    ),
    (
        "unknown surface: module app.broken (app/broken.py:3): source could not be parsed: "
        "SyntaxError under Python 3.11.10",
        "unknown surface: module app.broken (app/broken.py): source could not be parsed: "
        "SyntaxError",
    ),
    (
        "unknown surface: module web.broken (src/broken.ts:1): The parser could not parse the "
        "TypeScript syntax. Source excerpt: ','",
        "unknown surface: module web.broken (src/broken.ts): The parser could not parse the "
        "source syntax.",
    ),
    (
        "unknown surface: module web.broken (src/broken.ts:2): The parser could not parse the "
        "source syntax. Source excerpt: 'f(a,' (parser version tree-sitter 0.25.2)",
        "unknown surface: module web.broken (src/broken.ts): The parser could not parse the "
        "source syntax.",
    ),
]


@pytest.mark.parametrize(("earlier", "current"), EARLIER_FORMS)
def test_an_item_in_an_earlier_form_selects_the_line_without_volatile_values(
    earlier: str, current: str
) -> None:
    """trial3-1. Acceptance: for each earlier form with a line number, a source excerpt,
    or a parser version, `answer_migrations.current_line` gives the current form, with and
    without a map prefix. The current form does not change. An answer with the earlier
    item and the digest of the current line answers the current line: it is not open,
    not stale, and not pending. `warnings` names the earlier item, but not an item about a
    test file."""
    for prefix in ("", "Web: "):
        item, now = prefix + earlier, prefix + current
        assert answer_migrations.current_line(item) == now
        assert answer_migrations.current_line(now) == now
        answer = Answer(items=(item,), reason="known", evidence="a" * 64)
        result = judgement.apply_answers([now], [answer], {now: "a" * 64})
        assert result.open == [] and result.stale == [] and result.pending == []
        named = any(item in warning for warning in answer_migrations.warnings([answer]))
        # `judgement` gives no line about a test file (issue 114). No warning names the item.
        assert named != bool(answer_migrations.retired(item))


# ---- trial3-2 and trial3-6: a type re-export of a declaration file ---------------------

TYPE_REEXPORTS = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": json.dumps({"name": "web", "imports": {"#types/*": "./types/*.d.ts"}}),
    "tsconfig.json": "{}",
    "types/x.d.ts": "export type X = string;\nexport type Y = number;\n",
    "types/z.d.ts": "export type Z = string;\n",
    "types/space.d.ts": "export type S = string;\n",
    "src/index.ts": (
        "export const a = 1\n"
        "export type { X } from '#types/x'\n"
        "import type { Y } from '#types/x'\n"
        "import type { Z as Zed } from '#types/z'\n"
        "import type * as Space from '#types/space'\n"
        "import { Gone } from '#types/gone'\n"
        "\n"
        "export type { Y, Zed }\n"
        "export type { Space }\n"
        "export { Gone }\n"
        "export { Value } from '#types/z'\n"
    ),
}
DECLARATION = (
    "the re-export target '{target}' is the declaration file {file}. A declaration file "
    "gives only types and has no module record. Names: {names}."
)


def test_a_type_reexport_of_a_declaration_file_gives_the_kind_type(tmp_path: Path) -> None:
    """trial3-2. Acceptance: each name of a type-only re-export without a module has the
    kind `type`, for a direct and an indirect re-export (X, Y, Zed, Space). A name that is
    not type-only keeps the kind `unknown` (Gone, Value). On 0a51437, each of these names
    had the kind `unknown`."""
    write_tree(tmp_path, TYPE_REEXPORTS)
    facts = extract.build(config.load(tmp_path))
    kinds = {n["name"]: n["kind"] for n in facts["components"]["web.index"]["names"]}
    assert kinds == {
        "a": "object",
        "X": "type",
        "Y": "type",
        "Zed": "type",
        "Space": "type",
        "Gone": "unknown",
        "Value": "unknown",
    }


def test_an_indirect_reexport_gives_the_record_of_a_direct_reexport(tmp_path: Path) -> None:
    """trial3-6. Acceptance: an indirect re-export (`import type { Y } from '#types/x'`,
    then `export type { Y, Zed }`) gives one record for each target of the statement, at
    the line of the statement, with the public names, as a direct re-export does. The
    namespace import `Space` and the missing target `#types/gone` also give their line and
    names. No record has the line 0. On 0a51437, `#types/z` gave a record at line 0 without
    names, and the names Y and Space gave no record."""
    write_tree(tmp_path, TYPE_REEXPORTS)
    facts = extract.build(config.load(tmp_path))
    head = "unknown surface: module web.index (src/index.ts): "
    gone = "the re-export target '#types/gone' is outside the extracted module set. Names: Gone."
    expected = [
        (2, DECLARATION.format(target="#types/x", file="types/x.d.ts", names="X")),
        (8, DECLARATION.format(target="#types/x", file="types/x.d.ts", names="Y")),
        (8, DECLARATION.format(target="#types/z", file="types/z.d.ts", names="Zed")),
        (9, DECLARATION.format(target="#types/space", file="types/space.d.ts", names="Space")),
        (10, gone),
        (11, DECLARATION.format(target="#types/z", file="types/z.d.ts", names="Value")),
    ]
    lines = [line for line in source_facts.unknown_fact_lines(facts) if "web.index" in line]
    assert lines == [head + reason for _line, reason in expected]
    located = source_facts.located_records(facts)
    assert [[found.line for found in located[head + reason]] for _line, reason in expected] == [
        [line] for line, _reason in expected
    ]


# ---- trial3-3: the extract summary counts pairs, not test functions ---------------------


def test_the_extract_summary_tells_that_a_test_function_counts_for_each_module(
    tmp_path: Path,
) -> None:
    """trial3-3. Acceptance: one test function that imports 3 modules gives the sum 3 of
    `tests_total`. The summary row gives 3 with words that tell that the number counts
    one for each pair of a test function and a module. It does not say "3 test
    functions". On 0a51437, the row said "3 test functions import a module"."""
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/a.py": "def a() -> int:\n    return 1\n",
            "pkg/b.py": "def b() -> int:\n    return 2\n",
            "pkg/c.py": "def c() -> int:\n    return 3\n",
            "tests/test_all.py": (
                "from pkg.a import a\nfrom pkg.b import b\nfrom pkg.c import c\n\n\n"
                "def test_all() -> None:\n    assert a() + b() + c() == 6\n"
            ),
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert sum(c["tests_total"] for c in facts["components"].values()) == 3
    [row] = [line for line in facts_file.summary(facts) if line.startswith("  tests:")]
    assert "3 test functions" not in row
    assert row == (
        "  tests:            3 pairs of a test function and a module that it imports, "
        "0 in a test file with the module name"
    )


# ---- trial3-4: the number of history samples depends on commit activity -----------------


def test_a_period_without_commits_gives_no_history_sample(tmp_path: Path) -> None:
    """trial3-4. Acceptance: with `every_days` 7, four commits in one week give one sample
    and the last commit (2 samples). Four commits one week apart give 4 samples. A period
    of 8 weeks without commits gives no sample. Thus commit activity changes the number of
    samples, and the docstring of `history.sample` must not say that it does not."""
    _dated_repo(tmp_path / "busy", ["2024-01-01", "2024-01-02", "2024-01-03", "2024-03-01"])
    _dated_repo(tmp_path / "even", ["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"])
    assert len(history.sample(tmp_path / "busy", "2020-01-01", 7)) == 2
    assert len(history.sample(tmp_path / "even", "2020-01-01", 7)) == 4
    words = " ".join((history.sample.__doc__ or "").split())
    assert "does not change the number of samples" not in words


# ---- trial3-5: the default export of a call result --------------------------------------


def test_the_interface_hint_names_the_public_name_of_a_local_name() -> None:
    """trial3-5. Acceptance: an interface that starts with the local name of a default
    export (`ky(...)`) gives an interface line, because `ky` is not a public name. The
    hint names `default`, the public name with the defining symbol `ky`. It does not name
    the nearest spelling (`Hooks`). On 0a51437, the hint named `Hooks`."""
    components = {
        "ky.index": {
            "file": "source/index.ts",
            "names": [
                {"name": "default", "kind": "object", "defined_as": "ky"},
                {"name": "Hooks", "kind": "type"},
                {"name": "isKyError", "kind": "function"},
            ],
        }
    }
    card = Component("Ky", "Sends requests.", implemented_by=("ky.index",), interface="ky(url)")
    problem = check.interface_problem(card, components)
    assert problem.startswith("Ky interface starts with ky, but none of its modules defines")
    assert problem.endswith(". The public name for the symbol ky is default")


# A module that gives the symbol `ky` under a different public name, in each language.
ALIASED = {
    "python": (
        {
            "pkg/__init__.py": "from pkg.core import ky as client\n",
            "pkg/core.py": "def ky() -> int:\n    return 1\n",
        },
        "pkg",
        "client",
    ),
    "typescript": (
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name": "web"}',
            "tsconfig.json": "{}",
            "src/index.ts": (
                "const create = () => () => 1\nexport type Hooks = string\n"
                "const ky = create()\nexport default ky\n"
            ),
        },
        "web.index",
        "default",
    ),
}


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_the_interface_hint_uses_the_extracted_defining_symbol(
    tmp_path: Path, language: str
) -> None:
    """trial3-5. Acceptance: in 2 of 2 languages, the extracted public name of the symbol
    `ky` (`client` in Python, `default` in TypeScript) is the hint of the interface line
    for `ky(url)`."""
    files, module, public = ALIASED[language]
    write_tree(tmp_path, files)
    facts = extract.build(config.load(tmp_path))
    card = Component("Ky", "Sends requests.", implemented_by=(module,), interface="ky(url)")
    problem = check.interface_problem(card, facts["components"])
    assert problem.endswith(f". The public name for the symbol ky is {public}"), problem


# ---- trial3-7: the fix line of the cause `syntax` -----------------------------------------


def test_the_syntax_fix_line_tells_the_two_possible_conditions() -> None:
    """trial3-7. Acceptance: the fix line of the cause `syntax` first tells the user to
    examine the source at the line. It tells the two conditions: if the source is not
    correct, correct it. If the source is correct, the parser cannot read it, and the user
    records an answer. No instruction to correct the source comes without its
    condition. On 0a51437, the line started with "correct the source"."""
    text = unknown_causes.FIX[unknown_causes.SYNTAX]
    sentences = [part.strip() for part in text.split(". ") if part.strip()]
    assert "examine the source at the line" in sentences[0]
    fixes = [s for s in sentences if "correct the source" in s or "correct it" in s]
    assert fixes and all(s.startswith("If the source is not correct") for s in fixes)
    assert any(s.startswith("If the source is correct") for s in sentences)
    assert "[judgement] answered" in text


# ---- trial3-8: a package bin that is a script file ----------------------------------------


def test_a_package_bin_that_is_a_script_file_has_its_own_cause(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial3-8. Acceptance: a package bin whose target is an existing JavaScript file with
    no source module gives the cause `script file`. Its fix line does not name
    [package_roots], and it tells the user to examine the file and to record an answer.
    A bin whose target file does not exist keeps the cause `target`. The line text does
    not change. On 0a51437, the two bins had the cause `target`, and the fix line told the
    user to add a directory to [package_roots]."""
    root = mapped_project(tmp_path, "typescript")
    bins = {"web": "src/cli.ts", "shim": "bin/shim.js", "gone": "dist/gone.js"}
    write_tree(
        root,
        {
            "package.json": json.dumps({"name": "@acme/web", "bin": bins}),
            "bin/shim.js": "#!/usr/bin/env node\nimport '../dist/cli.js'\n",
        },
    )
    assert main(["--root", str(root), "refresh"]) == 0
    out = _judge(root, capsys)
    causes = {row["line"]: row["cause"] for row in out["open"] if "package_bin" in row["line"]}
    reason = "The parser could not resolve the package.json bin target to a TypeScript module."
    assert causes == {
        f"unknown surface: package_bin gone -> dist/gone.js: {reason}": unknown_causes.TARGET,
        f"unknown surface: package_bin shim -> bin/shim.js: {reason}": unknown_causes.SCRIPT_FILE,
    }
    text = unknown_causes.FIX[unknown_causes.SCRIPT_FILE]
    assert "package_roots" not in text and "[judgement] answered" in text
    assert "Examine the file" in text
    capsys.readouterr()
    main(["--root", str(root), "judgement"])
    assert f"  fix: {text}" in capsys.readouterr().out
