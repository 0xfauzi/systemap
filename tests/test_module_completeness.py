"""Each module record tells if systemap read all of its source and resolved its imports.

Acceptance:
- A TypeScript module with a syntax error: `completeness.parsed` is `false`,
  `card_review.digest` is None, and `card_review.state` is not `current`.
- A Python module with a syntax error: `parse_error` is the same as before this change,
  `card_review.digest` is None, and `card_review.state` is not `current`.
- A Python module and a TypeScript module with local imports that do not resolve: the
  `completeness.unresolved_imports` list gives each of these imports as the source
  writes it. Third-party imports and standard-library imports are not in the list.
- A module that parses and has only resolved imports gives `parsed` `true` and an
  empty list.
- A module that does not parse gives `unresolved_imports` None (not known), in the two
  languages. A record without `completeness` is not parsed for a shared reader.
- All tests that were in the suite before this change give no failure.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from conftest import write_tree

from systemap import card_review, config, evidence, extract, python_imports, source_facts
from systemap.model import Component, Meaning, Model, source_parsed

COMPLETE = {"parsed": True, "line": 0, "reason": "", "unresolved_imports": []}


def _states(module: str, facts: dict[str, Any]) -> tuple[str | None, str, str]:
    card = Component("Reader", "Reads inputs.", implemented_by=(module,))
    model = Model((800, 600), (), (), (card,), (), ())
    meaning = Meaning({"Reader": "Reader"})
    reviewed = dataclasses.replace(card, source_review="0" * 64)
    reviewed_model = Model((800, 600), (), (), (reviewed,), (), ())
    return (
        card_review.digest(card, model, meaning, facts),
        card_review.state(card, model, meaning, facts),
        card_review.state(reviewed, reviewed_model, meaning, facts),
    )


TYPESCRIPT_TREE = {
    "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/broken.ts": 'import { ok } from "./ok";\nexport function broken( {',
    "src/ok.ts": "export const ok = 1;\n",
    "src/reader.ts": (
        'import { ok } from "./ok";\n'
        'import { gone } from "./missing";\n'
        'import { lost } from "@/lost";\n'
        'import { z } from "zod";\n'
        'import fs from "node:fs";\n'
        'export { other } from "./also-missing";\n'
        "export async function read(): Promise<unknown> {\n"
        '  return [ok, gone, lost, z, fs, await import("./lazy-missing")];\n'
        "}\n"
    ),
}


def test_typescript_module_that_does_not_parse_gets_no_review_digest(tmp_path: Path) -> None:
    write_tree(tmp_path, TYPESCRIPT_TREE)
    facts = extract.build(config.load(tmp_path))
    broken = facts["components"]["web.broken"]
    assert broken["completeness"]["parsed"] is False
    assert broken["completeness"]["line"] == 2
    assert "could not parse the source syntax" in broken["completeness"]["reason"]
    # A TypeScript parse failure does not use the Python-only field.
    assert "parse_error" not in broken
    assert broken["completeness"]["unresolved_imports"] is None
    assert not source_parsed(broken)
    digest, state, reviewed_state = _states("web.broken", facts)
    assert digest is None
    assert state != card_review.CURRENT
    assert reviewed_state != card_review.CURRENT
    # A module that parses still gets a digest.
    assert facts["components"]["web.ok"]["completeness"] == COMPLETE
    assert _states("web.ok", facts)[0] is not None
    assert "source inventory unresolved: web.broken (src/broken.ts)" in (
        source_facts.inventory_issue_lines(facts)
    )
    ref = f"web.broken@{broken['source_sha256']}"
    assert not evidence._resolves(ref, facts)


def test_python_module_that_does_not_parse_keeps_its_result(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/bad.py": "def broken(:\n"})
    facts = extract.build(config.load(tmp_path))
    bad = facts["components"]["pkg.bad"]
    assert bad["parse_error"]["line"] == 1
    assert bad["parse_error"]["reason"] == "source could not be parsed: SyntaxError"
    assert bad["completeness"] == {
        "parsed": False,
        "line": 1,
        "reason": "source could not be parsed: SyntaxError",
        "unresolved_imports": None,
    }
    digest, state, reviewed_state = _states("pkg.bad", facts)
    assert digest is None
    assert state != card_review.CURRENT
    assert reviewed_state != card_review.CURRENT


def test_python_imports_that_do_not_resolve_are_listed(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/b.py": "def f(): ...\n",
            "pkg/space/inner.py": "X = 1\n",
            "pkg/a.py": (
                "import os\n"
                "import requests\n"
                "import pkg.missing\n"
                "import pkg.space\n"
                "from pkg import b\n"
                "from pkg.b import f\n"
                "from pkg.gone import x\n"
                "from .nothere import y\n"
                "from . import b as same\n"
                "from ...toofar import z\n"
            ),
        },
    )
    facts = extract.build(config.load(tmp_path))
    record = facts["components"]["pkg.a"]
    assert record["completeness"] == {
        **COMPLETE,
        "unresolved_imports": ["...toofar", ".nothere", "pkg.gone", "pkg.missing"],
    }
    assert record["external"] == ["requests"]
    assert facts["components"]["pkg.b"]["completeness"] == COMPLETE


def test_python_relative_import_above_the_top_package_has_no_source() -> None:
    assert python_imports.relative_source("pkg.sub.deep.a", False, 1, "x") == "pkg.sub.deep.x"
    assert python_imports.relative_source("pkg.sub.deep.a", False, 3, "") == "pkg"
    assert python_imports.relative_source("pkg.sub.deep.a", False, 4, "x") is None
    assert python_imports.relative_source("pkg.sub.deep.a", False, 5, "x") is None
    assert python_imports.relative_source("pkg", True, 1, "x") == "pkg.x"


def test_typescript_imports_that_do_not_resolve_are_listed(tmp_path: Path) -> None:
    write_tree(tmp_path, TYPESCRIPT_TREE)
    facts = extract.build(config.load(tmp_path))
    record = facts["components"]["web.reader"]
    assert record["completeness"] == {
        **COMPLETE,
        "unresolved_imports": ["./also-missing", "./lazy-missing", "./missing", "@/lost"],
    }
    assert record["uses"] == {"web.ok": ["ok"]}
    assert record["external"] == ["zod"]


def test_a_record_without_completeness_has_an_unknown_parse_state() -> None:
    assert not source_parsed({"syntax_sha": "one"})
    assert not source_parsed({"parse_error": {"line": 1}})
    assert not source_parsed({"completeness": {"parsed": False}})
    assert source_parsed({"completeness": dict(COMPLETE)})
