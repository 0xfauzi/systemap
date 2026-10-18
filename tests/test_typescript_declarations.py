"""Regression tests for declaration imports in issue #91."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, extract, unknown_causes

ROOTS = 'language = "typescript"\n[package_roots]\n"src" = "app"\n'


@pytest.mark.parametrize(
    ("specifier", "target"),
    [
        ("./types.d", "types.d.ts"),
        ("./types", "types.d.ts"),
        ("./types.js", "types.d.ts"),
        ("./types.jsx", "types.d.ts"),
        ("./types.d.ts", "types.d.ts"),
        ("./types.mjs", "types.d.mts"),
        ("./types.cjs", "types.d.cts"),
        ("./types", "types/index.d.ts"),
        ("@types", "types.d.ts"),
    ],
)
def test_declaration_import_has_no_module_or_unresolved_finding(
    tmp_path: Path, specifier: str, target: str
) -> None:
    """Acceptance: a declaration import gives no module, use, or unresolved finding."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": '{"compilerOptions":{"paths":{"@types":["./src/types"]}}}',
            f"src/{target}": "export interface Value { name: string }\n",
            "src/main.ts": f'import type {{ Value }} from "{specifier}";\n'
            "export function read(value: Value): string { return value.name; }\n",
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert set(facts["components"]) == {"app.main"}
    record = facts["components"]["app.main"]
    assert record["uses"] == {}
    assert record["external"] == []
    assert record["completeness"]["unresolved_imports"] == []


def test_relative_declaration_reexport_keeps_an_unknown_surface(tmp_path: Path) -> None:
    """Acceptance: a declaration re-export retains its public name and declaration cause."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/types.d.ts": "export interface Value { name: string }\n",
            "src/main.ts": 'export type { Value } from "./types.d";\n',
        },
    )
    record = extract.build(config.load(tmp_path))["components"]["app.main"]
    assert record["names"][0]["name"] == "Value"
    assert record["unknown"][0]["cause"] == unknown_causes.DECLARATION_FILE
    assert "src/types.d.ts" in record["unknown"][0]["reason"]
    assert record["completeness"]["unresolved_imports"] == []


def test_missing_declaration_stays_unresolved(tmp_path: Path) -> None:
    """Acceptance: a missing declaration file still gives an unresolved import."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/main.ts": 'import type { Value } from "./types.d";\nexport const x = 1;\n',
        },
    )
    record = extract.build(config.load(tmp_path))["components"]["app.main"]
    assert record["completeness"]["unresolved_imports"] == ["./types.d"]


def test_source_file_has_priority_over_a_declaration(tmp_path: Path) -> None:
    """Acceptance: a source file has priority over a declaration with the same stem."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/types.ts": "export interface Value { name: string }\n",
            "src/types.d.ts": "export interface Value { other: number }\n",
            "src/main.ts": 'import type { Value } from "./types.js";\nexport const x = 1;\n',
        },
    )
    record = extract.build(config.load(tmp_path))["components"]["app.main"]
    assert record["uses"] == {"app.types": ["Value"]}
    assert record["completeness"]["unresolved_imports"] == []


def test_declaration_target_stops_alias_fallback(tmp_path: Path) -> None:
    """Acceptance: the first alias target wins, even when only its declaration exists."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": '{"compilerOptions":{"paths":{"@types":["./src/types","./src/fallback"]}}}',
            "src/types.d.ts": "export interface Value { name: string }\n",
            "src/fallback.ts": "export interface Value { other: number }\n",
            "src/main.ts": 'import type { Value } from "@types";\nexport const x = 1;\n',
        },
    )
    record = extract.build(config.load(tmp_path))["components"]["app.main"]
    assert record["uses"] == {}
    assert record["completeness"]["unresolved_imports"] == []


def test_declaration_file_has_priority_over_a_directory_index(tmp_path: Path) -> None:
    """Acceptance: a declaration file has priority over a source directory index."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/types.d.ts": "export interface Value { name: string }\n",
            "src/types/index.ts": "export interface Value { other: number }\n",
            "src/main.ts": 'import type { Value } from "./types";\nexport const x = 1;\n',
        },
    )
    record = extract.build(config.load(tmp_path))["components"]["app.main"]
    assert record["uses"] == {}
    assert record["completeness"]["unresolved_imports"] == []
