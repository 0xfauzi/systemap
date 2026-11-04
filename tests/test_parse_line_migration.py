"""The finding line for a source parse error does not name one language.

Before this change, `source_facts.unknown_fact_lines` wrote "... under Python 3.11" for
a `parse_error` record. Shared logic must not name one language in a finding line. The
line then ended with "(parser version 3.11)". Facts format 11 removes the parser
version and the line number from the line (trial3-1), because they change while the
finding stays the same. 2.0.0 and 3.0.0 also read an answer item in `[judgement]
answered` that has the earlier form. From 3.1.0, systemap does not read that form.

Acceptance: the Python fixture and the TypeScript fixture each give an unknown-surface
line that does not contain "Python" or "under". An earlier-form item selects no line: it
is stale, the current line is open, and the item gets no warning. An item in the current
form with the prefix of the top map still selects the one current line in the nested map.
"""

from __future__ import annotations

import sys
from pathlib import Path

from conftest import TINY_PACKAGE, write_tree

from systemap import answer_migrations, config, extract, judgement, source_facts
from systemap.config import Answer


def _python_line(tmp_path: Path) -> str:
    write_tree(tmp_path, {**TINY_PACKAGE, "pkg/broken.py": "def broken(:\n    pass\n"})
    facts = extract.build(config.load(tmp_path))
    lines = [line for line in source_facts.unknown_fact_lines(facts) if "pkg.broken" in line]
    assert len(lines) == 1
    return lines[0]


def test_the_python_parse_error_line_names_no_language(tmp_path: Path) -> None:
    line = _python_line(tmp_path)
    assert line == (
        "unknown surface: module pkg.broken (pkg/broken.py): source could not be parsed: "
        "SyntaxError"
    )
    assert "Python" not in line


def test_the_typescript_parse_error_line_has_the_same_form(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "src/broken.ts": "export function broken( {\n",
        },
    )
    facts = extract.build(config.load(tmp_path))
    lines = [line for line in source_facts.unknown_fact_lines(facts) if "web.broken" in line]
    assert lines and all(
        line.startswith("unknown surface: module web.broken (src/broken.ts): ") for line in lines
    )
    assert not any("under Python" in line for line in lines)


def test_an_answer_in_the_earlier_form_selects_no_line(tmp_path: Path) -> None:
    line = _python_line(tmp_path)
    head, _, rest = line.partition("): ")
    earlier = f"{head}:1): {rest} under Python {sys.version.split()[0]}"
    assert answer_migrations.current_line(earlier) == earlier
    assert answer_migrations.current_line(line) == line
    evidence = {line: "digest-of-the-evidence"}
    answer = Answer(items=(earlier,), reason="known", evidence="digest-of-the-evidence")
    result = judgement.apply_answers([line], [answer], evidence)
    assert result.open == [line] and result.stale == [earlier] and result.pending == []
    assert answer_migrations.warnings([answer]) == []
    assert answer_migrations.warnings([Answer(items=(line,), reason="known")]) == []


def test_an_answer_follows_a_line_that_moved_to_a_nested_map() -> None:
    """Acceptance: an item with the prefix of the top map selects the one current line in
    the nested map. The form migration does not change the moved item again.
    """
    current = "sub: unknown surface: module app.broken (app/broken.py): SyntaxError"
    earlier = "unknown surface: module app.broken (app/broken.py): SyntaxError"
    answer = Answer(items=(earlier,), reason="known", evidence="digest-of-the-evidence")
    (moved,) = answer_migrations.current_lines([answer], [current])
    assert moved.items == (current,)
    assert answer_migrations.current_line(moved.items[0]) == current
    result = judgement.apply_answers([current], [moved], {current: "digest-of-the-evidence"})
    assert result.open == [] and result.stale == [] and result.pending == []
