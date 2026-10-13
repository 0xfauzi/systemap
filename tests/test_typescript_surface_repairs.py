"""Tests for the Codex results on the TypeScript public-surface reader.

Each test name gives the result ID. Each test failed on `origin/main` at d4b1514.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import change, check, config, extract
from systemap.model import Component
from systemap.typescript import TYPESCRIPT, parse_surface
from systemap.typescript import test_names as names_of_tests

ROOTS = 'language = "typescript"\n[package_roots]\n"src" = "app"\n'


def build(root: Path, files: dict[str, str]) -> dict[str, Any]:
    write_tree(root, {"systemap.toml": ROOTS, "tsconfig.json": "{}", **files})
    return extract.build(config.load(root))


def surface(source: str) -> dict[str, Any]:
    found = parse_surface(source, "src/m.ts")
    assert found is not None
    return found


def kinds(found: dict[str, Any]) -> list[tuple[str, str]]:
    return [(entry["name"], entry["kind"]) for entry in found["names"]]


def test_adapters_9_function_expression_uses_the_variable_name(tmp_path: Path) -> None:
    """Acceptance: `export const serve = function worker() {}` gives the public name
    `serve` in `names`, in `functions`, and in the entry points. It does not give `worker`.
    """
    found = surface("export const serve = function worker() {};\n")
    assert kinds(found) == [("serve", "function")]
    assert [f["name"] for f in found["functions"]] == ["serve"]
    facts = build(tmp_path, {"src/index.ts": "export const serve = function worker() {};\n"})
    points = {p["name"] for p in facts["entry_points"] if p["module"] == "app.index"}
    assert points == {"serve"}


def test_adapters_10_generator_variable_is_a_function() -> None:
    """Acceptance: `export const iterate = function* () {}` has kind `function` in `names`,
    one `functions` record, and the bucket `operations` in `api`.
    """
    found = surface("export const iterate = function* () {};\n")
    assert kinds(found) == [("iterate", "function")]
    assert [f["name"] for f in found["functions"]] == ["iterate"]
    assert [(a["name"], a["bucket"]) for a in found["api"]] == [("iterate", "operations")]


def test_adapters_11_default_export_of_a_local_name_has_its_fingerprint() -> None:
    """Acceptance: a parameter type change of `serve` gives `default` in the changed
    operations when the module has `export default serve`.
    """
    before = "function serve(x: string) {}\nexport default serve;\n"
    after = "function serve(x: number) {}\nexport default serve;\n"
    delta = change.surface_delta(before, after, TYPESCRIPT, "src/m.ts")
    assert delta is not None
    assert delta["changed"]["operations"] == ["default"]


def test_adapters_12_removed_star_reexport_is_a_surface_change() -> None:
    """Acceptance: a removed `*` re-export gives `*` in the removed constants, for a
    TypeScript fixture and for a Python fixture.
    """
    typescript = change.surface_delta(
        'export * from "./service";\n', "export {};\n", TYPESCRIPT, "src/m.ts"
    )
    python = change.surface_delta(
        "from .service import *\n", '"""Empty."""\n', extract.PYTHON, "pkg/__init__.py"
    )
    for delta in (typescript, python):
        assert delta is not None
        assert delta["removed"]["constants"] == ["*"]


def test_adapters_13_local_export_clause_records_the_declaration(tmp_path: Path) -> None:
    """Acceptance: `export { Store }` and `export { Store as Public }` give class records
    with the method `get()`. The interface `Store.get()` and `Public.get()` pass.
    """
    source = (
        "class Store { get(): number { return 1; } }\n"
        "function serve(): void {}\n"
        "export { Store, Store as Public, serve as start };\n"
    )
    found = surface(source)
    assert found["classes"] == [
        {"name": "Store", "methods": ["get(): number"]},
        {"name": "Public", "methods": ["get(): number"]},
    ]
    assert [f["name"] for f in found["functions"]] == ["start"]
    facts = build(tmp_path, {"src/store.ts": source})
    for interface in ("Store.get()", "Public.get()"):
        component = Component(
            id="Store", does="d", interface=interface, implemented_by=("app.store",)
        )
        assert check.interface_problem(component, facts["components"]) == ""


def test_adapters_16_type_only_reexports_keep_the_flag(tmp_path: Path) -> None:
    """Acceptance: each type-only re-export form has `type_only` set to true in `names`.
    The other re-exports have no `type_only` field. A named type-only re-export of a
    function gives no `public_function` entry point.
    """
    found = surface(
        'export type * from "./a";\n'
        'export type * as types from "./b";\n'
        'export type { serve } from "./c";\n'
        'export { type Store, run } from "./d";\n'
        'export * from "./e";\n'
    )
    assert [(entry["name"], entry.get("type_only", False)) for entry in found["names"]] == [
        ("*", True),
        ("types", True),
        ("serve", True),
        ("Store", True),
        ("run", False),
        ("*", False),
    ]
    facts = build(
        tmp_path,
        {
            "src/index.ts": 'export type { serve } from "./service";\nexport { run } from "./service";\n',
            "src/service.ts": "export function serve(): void {}\nexport function run(): void {}\n",
        },
    )
    points = {p["name"] for p in facts["entry_points"] if p["module"] == "app.index"}
    assert points == {"run"}


def test_adapters_21_string_literals_keep_their_escapes(tmp_path: Path) -> None:
    """Acceptance: a test name and an import path with escape sequences give the full
    decoded text: `user's order` and the module `app.xy`.
    """
    assert names_of_tests("it('user\\'s order', () => {});\n", "a.test.ts") == ["user's order"]
    facts = build(
        tmp_path,
        {
            "src/index.ts": 'import { a } from "./x\\u0079";\nexport { b } from "./x\\x79";\n',
            "src/xy.ts": "export const a = 1;\nexport const b = 2;\n",
        },
    )
    index = facts["components"]["app.index"]
    assert "app.xy" in index["uses"]
    assert [(n["name"], n.get("reexport_of")) for n in index["names"]] == [("b", "app.xy")]


def test_adapters_21_string_value_decodes_each_escape_form() -> None:
    """Acceptance: each escape form of the JavaScript grammar gives its character. A line
    continuation gives no character, and a surrogate pair gives one character.
    """
    found = surface("export { a } from './\\x61\\u0062\\u{63}\\'\\\\\\0\\q\\\nd\\ud83d\\ude00';\n")
    assert found["names"][0]["reexport_of"] == "./abc'\\\x00qd\U0001f600"


def test_adapters_16_type_only_local_exports_and_imports_keep_the_flag() -> None:
    """Acceptance: `export type { name }`, `export { type name }`, and an export of a
    type-only import have `type_only` set to true. A value export of the same name has a
    different `api` fingerprint.
    """
    found = surface(
        'import type { Order } from "./order";\n'
        'import { type Line, total } from "./line";\n'
        "function serve(): void {}\n"
        "class Store {}\n"
        "export type { serve };\n"
        "export { type Store, Order, Line, total };\n"
    )
    assert [(entry["name"], entry.get("type_only", False)) for entry in found["names"]] == [
        ("serve", True),
        ("Store", True),
        ("Order", True),
        ("Line", True),
        ("total", False),
    ]
    value = surface("function serve(): void {}\nexport { serve };\n")
    typed = surface("function serve(): void {}\nexport type { serve };\n")
    assert value["api"][0]["fingerprint"] != typed["api"][0]["fingerprint"]


def test_adapters_13_local_constant_has_the_kind_of_a_declared_export() -> None:
    """Acceptance: `const MAX = 3; export { MAX }` gives the same name and constant record
    as `export const MAX = 3`.
    """
    local = surface("const MAX = 3;\nexport { MAX };\n")
    declared = surface("export const MAX = 3;\n")
    assert kinds(local) == kinds(declared) == [("MAX", "constant")]
    assert local["constants"] == declared["constants"] == [{"name": "MAX", "value": "3"}]


SERVICE = "export function serve(): void {}\n"


@pytest.mark.parametrize(
    "files",
    [
        {"src/index.ts": 'export type * from "./service";\n'},
        {
            "src/index.ts": 'export * from "./barrel";\n',
            "src/barrel.ts": 'export type * from "./service";\n',
        },
        {
            "src/index.ts": 'export type * from "./barrel";\n',
            "src/barrel.ts": 'export * from "./service";\n',
        },
    ],
)
def test_a_type_only_star_reexport_stays_type_only_after_resolution(
    tmp_path: Path, files: dict[str, str]
) -> None:
    """Acceptance: `export type * from "./service"`, through one barrel or through a chain
    of two, gives the resolved name `serve` with `type_only` set to true, and no `serve`
    entry point in `app.index`.
    """
    facts = build(tmp_path, {**files, "src/service.ts": SERVICE})
    names = facts["components"]["app.index"]["names"]
    assert [(n["name"], n.get("type_only", False)) for n in names] == [("serve", True)]
    points = {p["name"] for p in facts["entry_points"] if p["module"] == "app.index"}
    assert "serve" not in points


def test_a_named_reexport_of_a_type_only_link_is_type_only(tmp_path: Path) -> None:
    """Acceptance: a named re-export whose chain has a type-only link has `type_only` set
    to true, and `app.index` has no `serve` entry point.
    """
    facts = build(
        tmp_path,
        {
            "src/index.ts": 'export { serve } from "./barrel";\n',
            "src/barrel.ts": 'export type { serve } from "./service";\n',
            "src/service.ts": SERVICE,
        },
    )
    (entry,) = facts["components"]["app.index"]["names"]
    assert entry["name"] == "serve" and entry.get("type_only") is True
    points = {p["name"] for p in facts["entry_points"] if p["module"] == "app.index"}
    assert "serve" not in points
