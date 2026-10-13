"""The `classes` fact holds only class declarations, with the same meaning for each language.

Codex result adapters-28: the TypeScript adapter recorded interfaces, enums, and type
aliases in `classes`. Thus `export type Text = string` gave one class in the extraction
summary. A type declaration that is not a class goes into `types`, with an explicit
`category`.

Acceptance: in the TypeScript fixture, `classes` holds only `Store`, and `types` holds
`Reader` (interface), `Text` (type_alias), and `Color` (enum). The summary gives 1 class
and 3 types. In the Python fixture, `classes` holds only `Request`, and `types` is empty.
Each consumer of `classes` also reads `types`: the interface rule finds `Reader.read`,
the facts view gives the kind `type`, and the audit context gives the category.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from conftest import TINY_PACKAGE, write_tree

from systemap import audit_code, check, config, extract, facts, facts_file
from systemap import language as languages

TYPESCRIPT_TREE = {
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/shapes.ts": (
        "export interface Reader { read(): string }\n"
        "export type Text = string;\n"
        "export enum Color { Red }\n"
        'export class Store { get(): string { return "" } }\n'
    ),
}


def _typescript_record(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    write_tree(tmp_path, TYPESCRIPT_TREE)
    found = extract.build(config.load(tmp_path))
    return found, found["components"]["web.shapes"]


def test_typescript_type_declarations_are_not_classes(tmp_path: Path) -> None:
    found, record = _typescript_record(tmp_path)
    assert record["classes"] == [{"name": "Store", "methods": ["get(): string"]}]
    assert record["types"] == [
        {"name": "Reader", "category": "interface", "methods": ["read(): string"]},
        {"name": "Text", "category": "type_alias", "methods": []},
        {"name": "Color", "category": "enum", "methods": []},
    ]
    assert {n["name"]: n["kind"] for n in record["names"]} == {
        "Reader": "type",
        "Text": "type",
        "Color": "type",
        "Store": "class",
    }
    lines = facts_file.summary(found)
    assert "  classes:          1" in lines
    assert "  types:            3" in lines


def test_python_classes_stay_classes_and_types_is_empty(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    found = extract.build(config.load(tmp_path))
    record = found["components"]["pkg.reader"]
    assert [c["name"] for c in record["classes"]] == ["Request"]
    assert record["types"] == []
    assert all(r["types"] == [] for r in found["components"].values())
    assert "  types:            0" in facts_file.summary(found)


@pytest.mark.skipif(not hasattr(ast, "TypeAlias"), reason="the type statement needs Python 3.12")
def test_python_type_statement_is_a_type_alias() -> None:
    surface = extract.parse_surface("type Amount = int\n")
    assert surface is not None
    assert surface["types"] == [{"name": "Amount", "category": "type_alias", "methods": []}]
    assert surface["classes"] == []
    assert {"name": "Amount", "kind": "type"} in surface["names"]


def test_the_interface_rule_reads_type_methods(tmp_path: Path) -> None:
    _found, record = _typescript_record(tmp_path)
    assert check.method_names(record, "Reader") == {"read"}
    assert check.method_names(record, "Store") == {"get"}
    python = {"classes": [{"name": "Request", "methods": ["def send(self, body: str) -> None"]}]}
    assert check.method_names(python, "Request") == {"send"}


def test_the_facts_view_and_the_audit_context_name_the_category(tmp_path: Path) -> None:
    _found, record = _typescript_record(tmp_path)
    older = {key: value for key, value in record.items() if key != "names"}
    assert ("Reader", "type") in facts.kinds(older)
    assert ("Store", "class") in facts.kinds(older)
    signatures = audit_code._signatures(
        record, {"Reader", "read", "Text"}, languages.repository("typescript")
    )
    assert "interface Reader: read(): string" in signatures
    assert "type alias Text" in signatures
