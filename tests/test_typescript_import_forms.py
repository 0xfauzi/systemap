"""The TypeScript adapter gives the import form of each import, and the imports by a string value.

Acceptance (facts format 15, written before the build):

- Each case of the specification gives its form. The form is `type` only for a statement
  that the TypeScript compiler removes.
- A literal `import()` or `require()` call is `call` in a function body and `load` at the
  top level. A call with a different first argument gives a `dynamic_imports` record.
- The moved readers give the same `uses` as before for the TypeScript fixtures.
- A deep tree gives no RecursionError.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, extract, typescript_import_forms
from systemap.typescript_syntax import syntax_tree

FIXTURES = Path(__file__).parent / "fixtures"


def facts(source: str) -> Any:
    imports, calls = typescript_import_forms.read_imports(syntax_tree(source, "a.ts"), source)
    return typescript_import_forms.import_facts(imports, calls, lambda specifier: specifier)


def forms(source: str) -> dict[str, tuple[str, ...]]:
    return dict(facts(source).forms)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('import type { A } from "./x";\n', ("type",)),
        ('import { type A, type B } from "./x";\n', ("type",)),
        ('import { type A, B } from "./x";\n', ("load",)),
        ('import type X = require("./x");\n', ("type",)),
        ('import X = require("./x");\n', ("load",)),
        ('export type { A } from "./x";\n', ("type",)),
        ('export type * from "./x";\n', ("type",)),
        ('export { A } from "./x";\n', ("load",)),
        ('import "./x";\n', ("load",)),
        ('import type * as N from "./x";\n', ("type",)),
        ('import D, { type A } from "./x";\n', ("load",)),
        ('export async function f() { return import("./x"); }\n', ("call",)),
        ('const m = await import("./x");\n', ("load",)),
        ('export const f = () => require("./x");\n', ("call",)),
        ('class K { m() { return require("./x"); } }\n', ("call",)),
        ('class K { get g() { return require("./x"); } }\n', ("call",)),
        ('class K { constructor() { require("./x"); } }\n', ("call",)),
        ('class K { static { require("./x"); } }\n', ("load",)),
    ],
)
def test_the_form_of_one_import(source: str, expected: tuple[str, ...]) -> None:
    assert forms(source) == {"./x": expected}


def test_a_target_with_two_forms_has_both_forms() -> None:
    source = 'import type { A } from "./x";\nexport function f() { return import("./x"); }\n'
    assert forms(source) == {"./x": ("call", "type")}


def test_an_import_by_a_value_gives_a_record() -> None:
    found = facts("const name = 'a';\nexport const m = import(name);\n")
    assert found.forms == {}
    assert [dict(item) for item in found.dynamic] == [
        {"call": "import", "text": "", "target": "", "line": 2}
    ]


def test_a_template_without_substitutions_gives_its_text() -> None:
    found = facts("export const m = import(`./x`);\nconst n = require(`./${name}`);\n")
    assert [dict(item) for item in found.dynamic] == [
        {"call": "import", "text": "./x", "target": "./x", "line": 1},
        {"call": "require", "text": "", "target": "", "line": 2},
    ]


def _sources() -> list[str]:
    found = [path.read_text(encoding="utf-8") for path in sorted(FIXTURES.rglob("*.ts"))]
    found.append(
        'import type { A } from "./a";\nimport { type B, C } from "./b";\n'
        'import D = require("./d");\nexport * from "./e";\nexport { F } from "./f";\n'
        'export type * from "./g";\nfunction h() { return import("./h"); }\n'
        "const i = require(name);\n"
    )
    return found


def test_the_moved_readers_give_the_same_imports() -> None:
    for source in _sources():
        root = syntax_tree(source, "a.ts")
        imports, _calls = typescript_import_forms.read_imports(root, source)
        before = sorted((specifier, sorted(names)) for specifier, names in _imports_of(root))
        assert sorted((specifier, sorted(names)) for specifier, names, _ in imports) == before


def _imports_of(root: Any) -> list[tuple[str, set[str]]]:
    return list(typescript_import_forms._imports(root))


def test_a_deep_tree_gives_no_recursion_error() -> None:
    depth = 3000
    source = "export const f = " + "() => " * depth + 'require("./x");\n'
    assert forms(source) == {"./x": ("call",)}
    nested = "const v = " + "g(" * depth + 'import("./y")' + ")" * depth + ";\n"
    assert forms(nested) == {"./y": ("load",)}


def test_extraction_writes_the_facts_of_a_typescript_module(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/a.ts": "export type A = number;\nexport const b = 1;\n",
            "src/c.ts": "export const c = 2;\n",
            "src/main.ts": (
                'import type { A } from "./a";\nimport { b } from "./a";\n'
                'export function f(): A { return require("./c").c + b; }\n'
                "export const g = (name: string) => import(name);\n"
            ),
        },
    )
    built = extract.build(config.load(tmp_path))
    assert built["import_details"] == ["call", "dynamic", "type"]
    record = built["components"]["web.main"]
    assert record["import_forms"] == {"web.a": ["load", "type"], "web.c": ["call"]}
    assert record["dynamic_imports"] == [{"call": "import", "text": "", "target": "", "line": 4}]
    assert "import_forms" not in built["components"]["web.a"]
