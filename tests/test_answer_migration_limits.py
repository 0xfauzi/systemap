"""The patterns of `answer_migrations` select only the earlier lines (llm-5, regex-3).

Acceptance values:

1. Each pattern in `answer_migrations.EARLIER_FORMS` has one negative case below. The
   case is a current line that the earlier pattern changed to a different line. An exact
   answer for the case selects only its own line, through `judgement.apply_answers`.
   Before the change, the answer selected the other line, and the case stayed open.
2. If a pattern has its fixed text at its fixed position, the case stays the same also
   without the current lines.
3. On a hostile line of 132 KB, all the patterns together take less than 10 s. Before
   the change, they took more than 100 s (7.5 s, 15.2 s, and 83.4 s for three lines).
4. An item that is longer than `LONGEST_MIGRATED` stays the same. The patterns operate
   one time for each item, also if the answer is compared with many lines.
"""

from __future__ import annotations

import time

import pytest

from systemap import answer_migrations, audit, judgement
from systemap.config import Answer

# The name of each pattern, a current line, and the line that the earlier pattern gave.
NEGATIVE: dict[str, tuple[str, str]] = {
    "parser name": (
        "unknown surface: module web.a (src/a.ts): the re-export target './b' is outside "
        "the extracted module set. Names: x under Python 3.",
        "unknown surface: module web.a (src/a.ts): the re-export target './b' is outside "
        "the extracted module set. Names: x",
    ),
    "npm package": (
        "unknown surface: module web.a (src/a.ts): the re-export target './b' is outside "
        "the extracted module set. Names: c extends d): the npm tsconfig package could not "
        "be read",
        "unknown surface: module web.a (src/a.ts): the re-export target './b' is outside "
        "the extracted module set. Names: c extends d): the configuration package could not "
        "be read",
    ),
    "language syntax": (
        "unknown surface: module web.a (src/a.ts): the re-export target './b: The parser "
        "could not parse the TypeScript syntax.' is outside the extracted module set.",
        "unknown surface: module web.a (src/a.ts): the re-export target './b: The parser "
        "could not parse the source syntax.' is outside the extracted module set.",
    ),
    "parser version": (
        "unknown surface: module web.a (src/a.ts): the re-export target './b' is outside "
        "the extracted module set. Names: c (parser version 1)",
        "unknown surface: module web.a (src/a.ts): the re-export target './b' is outside "
        "the extracted module set. Names: c",
    ),
    "source excerpt": (
        "unknown surface: module web.a (src/a.ts): the re-export target './b: The parser "
        "could not parse the source syntax. Source excerpt: c' is outside the extracted "
        "module set.",
        "unknown surface: module web.a (src/a.ts): the re-export target './b: The parser "
        "could not parse the source syntax.",
    ),
    "module line number": (
        "unknown surface: module web.a (src/a:12): dynamic import",
        "unknown surface: module web.a (src/a): dynamic import",
    ),
    "test file line number": (
        "unknown surface: test file tests/a:3: source could not be read",
        "unknown surface: test file tests/a: source could not be read",
    ),
    "entry kind identifier": (
        "entry point 7 get_users into Api have no sequence (route) has no sequence (component Api)",
        "entry point 7 get users into Api have no sequence (route) has no sequence (component Api)",
    ),
    "provider pick": (
        "decision owner: pkg.x is claimed by no card; closest: Reader",
        "decision owner: pkg.x is claimed by no card",
    ),
    "decision kind name": (
        "unknown surface: jev flow: extends 'x': the configuration package could not be read",
        "unknown surface: decision flow: extends 'x': the configuration package could not be read",
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

# The patterns whose fixed text at its fixed position does not agree with the case.
ANCHORED = (
    "parser name",
    "npm package",
    "language syntax",
    "parser version",
    "source excerpt",
    "entry kind identifier",
)

# Hostile lines of about 132 KB.
HOSTILE = (
    "unknown surface: " + " extends" * 16500,
    "unknown surface: module m" + " Source excerpt: x" * 8250,
    "unknown surface: package_export a" + " -> b" * 26400,
    "unknown surface: module m (" + "): the re-export target x" * 5500,
    "unknown surface: module m (a): source could not be read: " + " Source excerpt: x" * 8250,
    "entry point 7 " + "a_" * 66000 + " into A",
)


def test_each_pattern_has_one_negative_case() -> None:
    """Acceptance 1."""
    assert {form.name for form in answer_migrations.EARLIER_FORMS} == set(NEGATIVE)


@pytest.mark.parametrize("name", sorted(NEGATIVE))
def test_an_exact_current_line_selects_only_its_line(name: str) -> None:
    """Acceptance 1."""
    line, other = NEGATIVE[name]
    lines = [line, other]
    assert answer_migrations.current_line(line, set(lines)) == line
    answer = Answer(items=(line,), reason="known", evidence="digest")
    result = judgement.apply_answers(lines, [answer], dict.fromkeys(lines, "digest"))
    assert (result.open, result.stale, result.pending) == ([other], [], [])


def test_an_exact_audit_line_selects_only_its_line() -> None:
    """Acceptance 1: `audit` uses the same rule."""
    line, other = NEGATIVE["provider pick"]
    found = [audit.Line(line), audit.Line(other)]
    answer = Answer(items=(line,), reason="known", evidence="digest")
    result = audit.apply_reviewed(found, [answer], {line: "digest", other: "digest"})
    assert ([x.text for x in result.open], result.stale, result.pending) == ([other], [], [])


@pytest.mark.parametrize("name", ANCHORED)
def test_a_current_line_with_the_earlier_text_in_a_name_stays_the_same(name: str) -> None:
    """Acceptance 2, with and without a nested-map prefix."""
    line, _other = NEGATIVE[name]
    for prefix in ("", "Sub: "):
        assert answer_migrations.current_line(prefix + line) == prefix + line


def test_the_patterns_are_linear_on_a_long_line() -> None:
    """Acceptance 3. Before the change, these lines took more than 100 s."""
    patterns = [form.pattern for form in answer_migrations.EARLIER_FORMS]
    start = time.perf_counter()
    for line in HOSTILE:
        for pattern in [*patterns, answer_migrations.TARGET_LINE]:
            pattern.match(line)
    assert time.perf_counter() - start < 10


def test_a_long_item_stays_the_same_and_each_item_is_read_one_time() -> None:
    """Acceptance 4."""
    earlier = "crossing import: A imports B in 3 modules and no flow connects them"
    long_item = earlier.replace(" A ", " A" + "a" * answer_migrations.LONGEST_MIGRATED + " ")
    assert answer_migrations.current_line(long_item) == long_item
    assert answer_migrations.current_line(earlier) != earlier
    answer_migrations._migrated.cache_clear()
    lines = [f"single module: C{i} contains only m{i}" for i in range(50)]
    judgement.apply_answers(lines, [Answer(items=(earlier,), reason="r")], {})
    assert answer_migrations._migrated.cache_info().misses == 1
