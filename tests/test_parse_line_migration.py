"""The finding line for a source parse error does not name one language.

Before this change, `source_facts.unknown_fact_lines` wrote "... under Python 3.11" for
a `parse_error` record. Shared logic must not name one language in a finding line. The
line now ends with "(parser version 3.11)". An answer item in `[judgement] answered`
that has the earlier form still selects the line, with the same evidence digest, and
the judgement report gives a warning that tells the person to change the item.

Acceptance: the Python fixture and the TypeScript fixture each give an unknown-surface
line that does not contain "Python" or "under". An earlier-form item is not stale, it
answers the current line, its recorded digest stays valid, and the warnings name it.
"""

from __future__ import annotations

import hashlib
import json
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
    parser = sys.version.split()[0]
    assert line == (
        "unknown surface: module pkg.broken (pkg/broken.py:1): source could not be parsed: "
        f"SyntaxError (parser version {parser})"
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
        line.startswith("unknown surface: module web.broken (src/broken.ts:") for line in lines
    )
    assert not any("under Python" in line for line in lines)


def test_an_answer_in_the_earlier_form_selects_the_current_line(tmp_path: Path) -> None:
    line = _python_line(tmp_path)
    head, _, parser = line.removesuffix(")").rpartition(" (parser version ")
    earlier = f"{head} under Python {parser}"
    assert answer_migrations.current_line(earlier) == line
    assert answer_migrations.current_line(f"sub: {earlier}") == f"sub: {line}"
    assert answer_migrations.current_line(line) == line
    evidence = {line: "digest-of-the-evidence"}
    answer = Answer(items=(earlier,), reason="known", evidence="digest-of-the-evidence")
    result = judgement.apply_answers([line], [answer], evidence)
    assert result.open == [] and result.stale == [] and result.pending == []
    # A group digest was recorded over the configured text and the evidence of each line.
    group = (earlier, "other line")
    recorded = [(earlier, "digest-of-the-evidence"), ("other line", "second")]
    expected = hashlib.sha256(json.dumps(recorded, sort_keys=True).encode()).hexdigest()
    assert judgement.answer_digest(group, {**evidence, "other line": "second"}) == expected
    assert any(earlier in warning for warning in answer_migrations.warnings([answer]))
    assert answer_migrations.warnings([Answer(items=(line,), reason="known")]) == []
