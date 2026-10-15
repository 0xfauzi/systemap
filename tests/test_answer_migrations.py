"""`answer_migrations` is the one migration path for earlier forms of a finding line.

Acceptance values:

1. Each earlier form has one pattern in `answer_migrations.EARLIER_FORMS` and one case in
   `TEXT_FORMS` below. The names agree. `current_line` changes each earlier line to the
   current line, and it keeps the current line.
2. The two forms that need the current lines (a line that moved to a nested map, and a
   re-export target line without names) have one test each, through
   `answer_migrations.current_lines`.
3. The behavior for recorded answers does not change: an item in an earlier form answers
   the current line, with the recorded evidence digest, and `warnings` names the item.
   This is also true for the decision lines of `audit`.
4. `decision_kinds` and `judgement_moves` have no line migration.
5. An answer for a line about a test file is stale. `retired` gives the cause.
"""

from __future__ import annotations

import importlib.util

import pytest

from systemap import answer_migrations, audit, decision_kinds, judgement
from systemap.config import Answer

# The name of each earlier form, an earlier line, and its current line.
TEXT_FORMS: dict[str, tuple[str, str]] = {
    "parser name": (
        "unknown surface: module pkg.a (pkg/a.py:2): source could not be parsed: "
        "SyntaxError under Python 3.11.10",
        "unknown surface: module pkg.a (pkg/a.py): source could not be parsed: SyntaxError",
    ),
    "npm package": (
        "unknown surface: tsconfig.json extends '@x/base': "
        "the npm tsconfig package could not be read",
        "unknown surface: tsconfig.json extends '@x/base': "
        "the configuration package could not be read",
    ),
    "language syntax": (
        "unknown surface: module web.a (src/a.ts): The parser could not parse the TypeScript "
        "syntax.",
        "unknown surface: module web.a (src/a.ts): The parser could not parse the source syntax.",
    ),
    "parser version": (
        "unknown surface: module web.a (src/a.ts): The parser could not parse the source "
        "syntax. Source excerpt: 'f(,)' (parser version 0.23.2)",
        "unknown surface: module web.a (src/a.ts): The parser could not parse the source syntax.",
    ),
    "source excerpt": (
        "unknown surface: module web.a (src/a.ts): The parser could not parse the source "
        "syntax. Source excerpt: 'f(,)'",
        "unknown surface: module web.a (src/a.ts): The parser could not parse the source syntax.",
    ),
    "module line number": (
        "unknown surface: module web.a (src/a.ts:254): dynamic import",
        "unknown surface: module web.a (src/a.ts): dynamic import",
    ),
    "test file line number": (
        "unknown surface: test file tests/a.spec.ts:3: source could not be read",
        "unknown surface: test file tests/a.spec.ts: source could not be read",
    ),
    "entry kind identifier": (
        "entry point 7 public_functions into Api have no sequence (component Api)",
        "entry point 7 public functions into Api have no sequence (component Api)",
    ),
    "provider pick": (
        "jev mis-fold: Parser claims pkg.parser, which reads like Reader",
        "decision mis-fold: Parser claims pkg.parser",
    ),
    "decision kind name": (
        "Core: jev flow: A -> B ('x'): the code where they meet may not carry it",
        "Core: decision flow: A -> B ('x'): the code where they meet may not carry it",
    ),
    "crossing count": (
        "crossing import: Skill imports Config in 3 modules and no flow connects them",
        "crossing import: Skill imports Config and no flow connects them",
    ),
    "package export count": (
        "unknown surface: package_export web -> dist/a.js (+2 more): 3 package.json export "
        "targets have no resolved TypeScript modules.",
        "unknown surface: package_export web -> dist/a.js: The package.json export targets "
        "have no resolved TypeScript modules.",
    ),
}


def test_each_earlier_form_has_one_pattern_and_one_case() -> None:
    """Acceptance 1."""
    names = [form.name for form in answer_migrations.EARLIER_FORMS]
    assert len(names) == len(set(names))
    assert set(names) == set(TEXT_FORMS)


@pytest.mark.parametrize("name", sorted(TEXT_FORMS))
def test_an_earlier_form_gives_the_current_line(name: str) -> None:
    """Acceptance 1, with and without a nested-map prefix."""
    earlier, current = TEXT_FORMS[name]
    for prefix in ("", "Sub: ") if not earlier.startswith("Core: ") else ("",):
        assert answer_migrations.current_line(prefix + earlier) == prefix + current
        assert answer_migrations.current_line(prefix + current) == prefix + current


def test_a_moved_line_selects_the_one_line_in_the_nested_map() -> None:
    """Acceptance 2: the earlier item has the prefix of the top map."""
    current = "sub: unknown surface: module app.broken (app/broken.py): SyntaxError"
    earlier = "unknown surface: module app.broken (app/broken.py): SyntaxError"
    answer = Answer(items=(earlier,), reason="known", evidence="digest")
    (moved,) = answer_migrations.current_lines([answer], [current])
    assert moved.items == (current,)


def test_a_target_line_without_names_selects_the_one_line_with_names() -> None:
    """Acceptance 2: the module, the file, and the target must agree with one line."""
    earlier = (
        "unknown surface: module web.index (src/index.ts:1): the re-export target "
        "'#types/missing' is outside the extracted module set."
    )
    current = (
        "unknown surface: module web.index (src/index.ts): the re-export target "
        "'#types/missing' is outside the extracted module set. Names: Missing."
    )
    [moved] = answer_migrations.current_lines([Answer(items=(earlier,), reason="r")], [current])
    assert moved.items == (current,)
    second = current.replace("Missing.", "Other.")
    [kept] = answer_migrations.current_lines(
        [Answer(items=(earlier,), reason="r")], [current, second]
    )
    assert kept.items == (earlier,)


@pytest.mark.parametrize("name", ["crossing count", "package export count"])
def test_an_answer_in_an_earlier_count_form_keeps_its_digest(name: str) -> None:
    """Acceptance 3."""
    earlier, current = TEXT_FORMS[name]
    answer = Answer(items=(earlier,), reason="known", evidence="digest")
    result = judgement.apply_answers([current], [answer], {current: "digest"})
    assert result.open == [] and result.stale == [] and result.pending == []
    assert any(earlier in warning for warning in answer_migrations.warnings([answer]))
    assert answer_migrations.warnings([Answer(items=(current,), reason="known")]) == []


def test_an_audit_answer_in_an_earlier_form_keeps_its_digest() -> None:
    """Acceptance 3: `audit` uses the same migration path."""
    earlier, current = TEXT_FORMS["provider pick"]
    answer = Answer(items=(earlier,), reason="known", evidence="digest")
    result = audit.apply_reviewed([audit.Line(current)], [answer], {current: "digest"})
    assert (result.open, result.answered, result.pending, result.stale) == ([], 1, [], [])


def test_only_answer_migrations_changes_a_line() -> None:
    """Acceptance 4."""
    assert not hasattr(decision_kinds, "current_line")
    assert importlib.util.find_spec("systemap.judgement_moves") is None


def test_an_answer_for_a_test_file_line_is_stale_with_a_cause() -> None:
    """Acceptance 5."""
    item = "unknown surface: test file tests/a.spec.ts:3: source could not be read"
    assert answer_migrations.retired(item) == "judgement gives no line about a test file"
    assert answer_migrations.retired("single module: A contains only a") == ""
    result = judgement.apply_answers([], [Answer(items=(item,), reason="r", evidence="d")], {})
    assert result.stale == [item]
    report = "\n".join(judgement.report(result))
    assert f"stale answer: '{item}' is no longer a finding: judgement gives no line" in report
