from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, extract
from systemap.typescript import parse_surface


def test_compiler_provenance_is_independent_of_checkout_path(tmp_path: Path) -> None:
    """Acceptance: two identical checkouts have exactly equal provenance."""
    tree = {
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
        "package.json": '{"name":"web"}',
        "tsconfig.json": json.dumps(
            {
                "compilerOptions": {
                    "baseUrl": ".",
                    "rootDirs": ["src", "generated"],
                    "outDir": "dist",
                    "paths": {"@/*": ["src/*"]},
                }
            }
        ),
        "src/entry.ts": "export const value = 1;",
    }
    snapshots = []
    for name in ("first", "second"):
        root = tmp_path / name
        write_tree(root, tree)
        snapshots.append(extract.build(config.load(root)))
    stored = tmp_path / "saved-facts.json"
    extract.write_facts(stored, snapshots[0])
    assert snapshots[0]["provenance"] == snapshots[1]["provenance"]
    assert extract.drift(snapshots[1], json.loads(stored.read_text())) == []
    (tmp_path / "second" / "tsconfig.json").write_text('{"compilerOptions":{"rootDirs":["src"]}}')
    changed = extract.build(config.load(tmp_path / "second"))
    assert "extraction inputs changed since the map was built" in extract.drift(
        changed, snapshots[0]
    )


@pytest.mark.parametrize("explicit_files", [False, True])
@pytest.mark.parametrize(
    ("importer", "specifier"),
    [
        ("src/generated/views/entry.ts", "./x"),
        ("outside/entry.ts", "../src/generated/views/x"),
    ],
)
def test_overlapping_root_dirs_use_longest_matching_root(
    tmp_path: Path, explicit_files: bool, importer: str, specifier: str
) -> None:
    """Acceptance: resolve the same target as TypeScript 5.9.3."""
    compiler: dict[str, object] = {"compilerOptions": {"rootDirs": ["src", "src/generated"]}}
    if explicit_files:
        compiler["files"] = [importer]
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"." = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": json.dumps(compiler),
            importer: f'import {{ value }} from "{specifier}"; export const result = value;',
            "src/views/x.ts": "export const value = 1;",
            "src/generated/generated/views/x.ts": "export const value = 2;",
        },
    )
    facts = extract.build(config.load(tmp_path))
    module = "web." + importer.removesuffix(".ts").replace("/", ".")
    assert facts["components"][module]["imports"] == ["web.src.views.x"]


@pytest.mark.parametrize(
    "declaration",
    [
        "export function run(value: number): number { return BODY; }",
        "export const run = (value: number): number => { return BODY; };",
        "export class Runner { static { console.log(BODY); } run(): number { return BODY; } }",
        "export class Runner { run = (value: number): number => { return BODY; }; }",
        "export class Runner { run = (value: number): number => BODY; }",
        "export namespace Nested { export function run(): number { return BODY; } }",
        "const hidden = BODY; export function run(): number { return hidden; }",
    ],
)
def test_namespace_api_ignores_implementation_changes(declaration: str) -> None:
    """Acceptance: zero public API changes for executable body edits."""
    first = parse_surface("export namespace Tools { " + declaration.replace("BODY", "1") + " }")
    second = parse_surface("export namespace Tools { " + declaration.replace("BODY", "2") + " }")
    assert first["api"] == second["api"]


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("export const LIMIT = 1;", "export const LIMIT = 2;"),
        (
            "export function run(value: number): number {}",
            "export function run(value: string): number {}",
        ),
        ("export interface Value { name: string }", "export interface Value { name: number }"),
        ("export const run = (value: number) => 1;", "export const run = (value: string) => 1;"),
        ("export class Runner { value = 1; }", "export class Runner { value = 2; }"),
        (
            "export class Runner { run = (value: number) => 1; }",
            "export class Runner { run = (value: string) => 1; }",
        ),
    ],
)
def test_namespace_api_retains_public_values_and_signatures(first: str, second: str) -> None:
    """Acceptance: each public value or signature edit changes the fingerprint."""
    assert (
        parse_surface(f"export namespace Tools {{ {first} }}")["api"]
        != parse_surface(f"export namespace Tools {{ {second} }}")["api"]
    )
