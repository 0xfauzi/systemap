"""`answer_migrations` is the one migration path for earlier forms of a finding line.

Acceptance values:

1. Each earlier form has one pattern in `answer_migrations.EARLIER_FORMS` and one case in
   `TEXT_FORMS` below. The names agree. `current_line` changes each earlier line to the
   current line, and it keeps the current line.
2. The two forms that need the current lines (a line that moved to a nested map, and a
   re-export target line without names) have one test each, through
   `answer_migrations.current_lines`. These items get no warning.
3. The behavior for recorded answers does not change: an item in an earlier form answers
   the current line, with the recorded evidence digest, and `warnings` names the item.
   This is also true for the decision lines of `audit`.
4. `decision_kinds` and `judgement_moves` have no line migration.
5. An answer for a line about a test file is stale. `retired` gives the cause.
6. From 3.1.0, the forms of the releases before 2.0.0 in `REMOVED` and the previous kind
   names of 2.0.0 and 3.0.0 in `RENAMED` select no line, and they get no migration
   warning. The current line is open, and the report gives the item as a stale answer
   with the action. For a previous kind name, the action gives the current line.
"""

from __future__ import annotations

import importlib.util

import pytest

from systemap import answer_migrations, audit, decision_kinds, judgement
from systemap.config import Answer

# The name of each earlier form, an earlier line, and its current line.
TEXT_FORMS: dict[str, tuple[str, str]] = {
    "provider pick": (
        "decision mis-fold: Parser claims pkg.parser, which reads like Reader",
        "decision mis-fold: Parser claims pkg.parser",
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
    "control character": (
        "unknown surface: package_bin t\nx\x1b -> ./a.js: The parser could not resolve the "
        "package.json bin target to a TypeScript module.",
        "unknown surface: package_bin t\\u000ax\\u001b -> ./a.js: The parser could not "
        "resolve the package.json bin target to a TypeScript module.",
    ),
}


# The earlier lines that 2.0.0 and 3.0.0 read, and that 3.1.0 does not read, with the
# current line of each one.
REMOVED = {
    "unknown surface: module pkg.a (pkg/a.py): source could not be parsed: "
    "SyntaxError under Python 3.11.10": "unknown surface: module pkg.a (pkg/a.py): source "
    "could not be parsed: SyntaxError",
    "unknown surface: tsconfig.json extends '@x/base': the npm tsconfig package could not "
    "be read": "unknown surface: tsconfig.json extends '@x/base': the configuration package "
    "could not be read",
    "unknown surface: module web.a (src/a.ts): The parser could not parse the TypeScript "
    "syntax.": "unknown surface: module web.a (src/a.ts): The parser could not parse the "
    "source syntax.",
    "unknown surface: module web.a (src/a.ts): The parser could not parse the source "
    "syntax. Source excerpt: 'f(,)' (parser version 0.23.2)": "unknown surface: module "
    "web.a (src/a.ts): The parser could not parse the source syntax.",
    "unknown surface: module web.a (src/a.ts): The parser could not parse the source "
    "syntax. Source excerpt: 'f(,)'": "unknown surface: module web.a (src/a.ts): The "
    "parser could not parse the source syntax.",
    "unknown surface: module web.a (src/a.ts:254): dynamic import": "unknown surface: "
    "module web.a (src/a.ts): dynamic import",
    "entry point 7 public_functions into Api have no sequence (component Api)": "entry "
    "point 7 public functions into Api have no sequence (component Api)",
}

# The items with a previous kind name, and the current line that the stale row gives.
# Releases before 2.0.0 put the pick of the provider at the end of a `jev` line.
RENAMED = {
    "jev mis-fold: Parser claims pkg.parser, which reads like Reader": (
        "decision mis-fold: Parser claims pkg.parser"
    ),
    "Core: jev owner: pkg.stray is claimed by no card; closest: Reader": (
        "Core: decision owner: pkg.stray is claimed by no card"
    ),
    "jev owner: pkg.stray is claimed by no card; it reads like none of the cards": (
        "decision owner: pkg.stray is claimed by no card"
    ),
    "Core: jev flow: A -> B ('x'): the code where they meet may not carry it": (
        "Core: decision flow: A -> B ('x'): the code where they meet may not carry it"
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
    assert answer_migrations.warnings([Answer(items=(earlier,), reason="r")], {current}) == []
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


@pytest.mark.parametrize("item", sorted(REMOVED))
def test_a_removed_form_selects_no_line_and_the_report_gives_the_action(item: str) -> None:
    """Acceptance 6: the current line is open, and the item is a stale answer."""
    current = REMOVED[item]
    answer = Answer(items=(item,), reason="r", evidence="d")
    assert answer_migrations.current_line(item) == item
    assert answer_migrations.warnings([answer]) == []
    assert answer_migrations.current_lines([answer], [current]) == [answer]
    result = judgement.apply_answers([current], [answer], {current: "d"})
    assert (result.open, result.stale) == ([current], [item])
    report = "\n".join(judgement.report(result))
    assert f"stale answer: '{item}' is now missing. Remove it from [judgement] answered." in (
        report
    )


@pytest.mark.parametrize("item", sorted(RENAMED))
def test_a_previous_kind_name_gives_the_current_line_in_the_stale_row(item: str) -> None:
    """Acceptance 6, for a previous kind name."""
    assert answer_migrations.current_line(item) == item
    assert answer_migrations.warnings([Answer(items=(item,), reason="r")]) == []
    assert answer_migrations.renamed_items([Answer(items=(item,), reason="r")]) == [item]
    assert answer_migrations.stale(item).endswith(
        f"which systemap does not read. Change it to '{RENAMED[item]}' in [judgement] answered."
    )
