"""Tests for the TypeScript public surface: exports, re-exports, test files and the
checks that read TypeScript facts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import write_tree

from systemap import check, config, extract, judgement
from systemap.model import Component, Model
from systemap.typescript import TYPESCRIPT, parse_surface
from systemap.typescript import test_names as names_of_tests

ROOTS = 'language = "typescript"\n[package_roots]\n"src" = "app"\n'


def build(root: Path, files: dict[str, str]) -> dict[str, Any]:
    write_tree(root, {"systemap.toml": ROOTS, "tsconfig.json": "{}", **files})
    return extract.build(config.load(root))


def names(record: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(n["name"], n["kind"], n.get("reexport_of", "")) for n in record["names"]]


def test_import_then_export_is_a_reexport(tmp_path: Path) -> None:
    """Acceptance: the same names and entry points as `export { ... } from "./service"`."""
    facts = build(
        tmp_path,
        {
            "src/index.ts": (
                'import { serve, Store } from "./service";\n'
                'import * as service from "./service";\n'
                'import run from "./run";\n'
                "export { serve, Store, service, run as start };\n"
            ),
            "src/service.ts": (
                "export function serve(): number { return 1; }\n"
                "export class Store { get(): number { return 1; } }\n"
            ),
            "src/run.ts": "export default function run(): void {}\n",
        },
    )
    index = facts["components"]["app.index"]
    assert names(index) == [
        ("serve", "function", "app.service"),
        ("Store", "class", "app.service"),
        ("service", "object", "app.service"),
        ("start", "function", "app.run"),
    ]
    assert "unknown" not in index or index["unknown"] == []
    points = {(p["name"], p["module"]) for p in facts["entry_points"]}
    assert {("serve", "app.index"), ("start", "app.index")} <= points


def test_named_reexport_reads_the_source_before_a_dotted_module(tmp_path: Path) -> None:
    """Acceptance: logger.config.ts does not hide the function `config` of logger.ts."""
    facts = build(
        tmp_path,
        {
            "src/index.ts": 'export { config, log } from "./logger";\n',
            "src/logger.ts": (
                "export function config(level: string): void { void level; }\n"
                "export function log(m: string): void { void m; }\n"
            ),
            "src/logger.config.ts": 'export const DEFAULT_LEVEL = "info";\n',
        },
    )
    assert names(facts["components"]["app.index"]) == [
        ("config", "function", "app.logger"),
        ("log", "function", "app.logger"),
    ]
    points = {p["name"] for p in facts["entry_points"] if p["module"] == "app.index"}
    assert points == {"config", "log"}


def test_explicit_export_hides_a_star_export_with_the_same_name(tmp_path: Path) -> None:
    """Acceptance: `tsc -p .` accepts this module and `import { X } from "./index"`."""
    facts = build(
        tmp_path,
        {
            "src/a.ts": "export function X(): number { return 1; }\nexport function onlyA(): void {}\n",
            "src/b.ts": "export function X(): number { return 2; }\nexport function onlyB(): void {}\n",
            "src/index.ts": 'export * from "./a";\nexport * from "./b";\nexport { X } from "./a";\n',
            "src/local.ts": 'export * from "./a";\nexport const X = 3;\n',
        },
    )
    index = facts["components"]["app.index"]
    assert sorted(names(index)) == [
        ("X", "function", "app.a"),
        ("onlyA", "function", "app.a"),
        ("onlyB", "function", "app.b"),
    ]
    assert index.get("unknown", []) == []
    assert sorted(names(facts["components"]["app.local"])) == [
        ("X", "object", ""),
        ("onlyA", "function", "app.a"),
    ]


def test_default_export_of_a_local_name_has_its_kind() -> None:
    """Acceptance: the same kind as `export { handler as default }`, with no unknown record."""
    for source, kind in (
        ("function handler() {}\nexport default handler;\n", "function"),
        ("class Repo {}\nexport default Repo;\n", "class"),
        ("export const Button = () => null;\nexport default Button;\n", "function"),
    ):
        surface = parse_surface(source, "x.tsx")
        assert surface is not None
        assert surface["names"][-1]["name"] == "default"
        assert surface["names"][-1]["kind"] == kind
        assert surface["unknown"] == []
    unknown = parse_surface("export default window.app;\n")
    assert unknown is not None and len(unknown["unknown"]) == 1


def test_export_type_star_and_variance_keep_the_surface(tmp_path: Path) -> None:
    """Acceptance: `tsc -p .` accepts both files, so the surface is known."""
    facts = build(
        tmp_path,
        {
            "src/index.ts": 'export type * from "./types";\nexport { serve } from "./service";\n',
            "src/types.ts": "export interface Order { id: string }\n",
            "src/service.ts": "export function serve(): number { return 1; }\n",
            "src/box.ts": "export interface Box<in out T> { v: T }\nexport class Sink<in T> {}\n",
        },
    )
    components = facts["components"]
    assert sorted(names(components["app.index"])) == [
        ("Order", "type", "app.types"),
        ("serve", "function", "app.service"),
    ]
    assert sorted(names(components["app.box"])) == [("Box", "type", ""), ("Sink", "class", "")]
    assert components["app.index"].get("unknown", []) == []
    assert components["app.box"].get("unknown", []) == []
    points = {p["name"] for p in facts["entry_points"]}
    assert "serve" in points


def test_reexport_from_an_npm_package_is_not_unknown(tmp_path: Path) -> None:
    """Acceptance: the target is an external package. A local target that is not found
    still gives an unknown record.
    """
    facts = build(
        tmp_path,
        {
            "src/index.ts": (
                'export { z } from "zod";\nexport * from "@radix-ui/react-dialog";\n'
                'export { gone } from "./missing";\n'
            ),
        },
    )
    index = facts["components"]["app.index"]
    assert names(index) == [("z", "unknown", "zod"), ("gone", "unknown", "./missing")]
    assert [issue["reason"] for issue in index["unknown"]] == [
        "the re-export target './missing' is outside the extracted module set."
    ]
    assert index["external"] == ["@radix-ui/react-dialog", "zod"]


def test_common_test_files_are_tests(tmp_path: Path) -> None:
    """Acceptance: the Jest `__tests__` folder, Cypress `.cy.ts` files and Vitest
    `.test.mts` files are tests, not source modules.
    """
    facts = build(
        tmp_path,
        {
            "src/svc/math.ts": "export function add(a: number, b: number): number { return a + b; }\n",
            "src/svc/__tests__/math.ts": (
                'import { add } from "../math";\ntest("adds two numbers", () => add(1, 2));\n'
            ),
            "src/svc/math.cy.ts": 'import { add } from "./math";\nit("adds in cypress", () => add(1, 2));\n',
            "src/svc/math.test.mts": 'import { add } from "./math.mjs";\ntest("adds in mts", () => add(1, 2));\n',
        },
    )
    assert sorted(facts["components"]) == ["app.svc.math"]
    assert facts["components"]["app.svc.math"]["tests_total"] == 3
    assert TYPESCRIPT.is_test_file("src/svc/__tests__/helper.ts", ())
    assert not TYPESCRIPT.is_test_file("src/svc/tests_helper.ts", ())


def test_docstring_is_the_first_comment_before_the_code() -> None:
    """Acceptance: a tool directive and a later comment are not the docstring. The
    comment marks are removed, and the first paragraph is kept.
    """
    doc = parse_surface(
        "#!/usr/bin/env node\n// eslint-disable-next-line no-console\n"
        "/**\n * Reads orders.\n * Writes records.\n *\n * More text.\n */\nexport const a = 1;\n"
    )
    assert doc is not None and doc["docstring"] == "Reads orders. Writes records."
    late = parse_surface('import x from "./x";\n// Not a module comment.\nexport const b = x;\n')
    assert late is not None and late["docstring"] == ""
    line = parse_surface("// Reads orders.\nexport const c = 1;\n")
    assert line is not None and line["docstring"] == "Reads orders."


def test_overload_signatures_give_one_public_name() -> None:
    """Acceptance: one name `pick`, and each signature in `functions`."""
    over = parse_surface(
        "export function pick(a: string): string;\nexport function pick(a: number): number;\n"
        "export function pick(a: any): any { return a; }\n"
    )
    assert over is not None and over["names"] == [{"name": "pick", "kind": "function"}]
    assert len(over["functions"]) == 3


def test_empty_export_has_no_unknown_record() -> None:
    """Acceptance: `export {}` only makes the file a module. It has no public name."""
    marker = parse_surface("declare global { var ready: boolean }\nexport {};\n")
    assert marker is not None and marker["unknown"] == [] and marker["names"] == []


def test_export_module_is_a_namespace() -> None:
    """Acceptance: `export module Legacy {}` is the same as `export namespace Legacy {}`."""
    legacy = parse_surface("export module Legacy { export const x = 1; }\n")
    assert legacy is not None and legacy["names"] == [{"name": "Legacy", "kind": "object"}]
    assert legacy["unknown"] == []


def test_table_and_template_test_names_are_counted() -> None:
    """Acceptance: `it.each(...)("name")` and a template literal name give a test name."""
    tests = names_of_tests(
        "it.each([[1, 2]])('adds %i', (a) => {});\n"
        "test.each`a | b`('table $a', () => {});\n"
        "test(`template name`, () => {});\n"
        "test(`case ${x}`, () => {});\n"
        "describe('suite', () => { it('plain', () => {}); });\n"
    )
    assert tests == ["adds %i", "table $a", "template name", "case ${x}", "plain"]


def test_node_built_in_modules_are_not_external(tmp_path: Path) -> None:
    """Acceptance: as the Python flow leaves out the standard library."""
    facts = build(
        tmp_path,
        {
            "src/io.ts": (
                'import fs from "node:fs";\nimport path from "path";\n'
                'import { readFile } from "fs/promises";\nimport { z } from "zod";\n'
                "export const all = [fs, path, readFile, z];\n"
            ),
        },
    )
    assert facts["components"]["app.io"]["external"] == ["zod"]


def test_typescript_method_headers_give_interface_methods() -> None:
    """Acceptance: `interface="UserService.getUser"` gives no finding for this class."""
    surface = parse_surface(
        "export class UserService {\n"
        "  async getUser(id: string): Promise<string> { return id; }\n"
        "  listUsers(): string[] { return []; }\n"
        "  static create<T>(): UserService { return new UserService(); }\n"
        "  get size(): number { return 0; }\n"
        "  async *pages() {}\n"
        "  get(key: string): string { return key; }\n"
        "  private secret(): void {}\n"
        "}\n"
    )
    assert surface is not None
    assert check.method_names(surface, "UserService") == {
        "getUser",
        "listUsers",
        "create",
        "size",
        "pages",
        "get",
    }
    components = {"app.users": surface}
    good = Component(
        id="Users", does="d", interface="UserService.getUser", implemented_by=("app.users",)
    )
    assert check.interface_problem(good, components) == ""
    bad = Component(
        id="Users", does="d", interface="UserService.secret", implemented_by=("app.users",)
    )
    assert "has no public method secret" in check.interface_problem(bad, components)


def test_typescript_model_sdk_packages() -> None:
    """Acceptance: npm model SDK packages give `model sdk` findings, as their Python
    import names do.
    """
    imports = [
        "@anthropic-ai/sdk",
        "@langchain/openai",
        "openai/resources",
        "ai",
        "@ai-sdk/openai",
        "@google/genai",
        "@google/generative-ai",
        "@mistralai/mistralai",
        "cohere-ai",
        "langchain/chat_models/openai",
        "react",
        "@anthropic-ai/claude-code",
        "aikido",
    ]
    assert [judgement.sdk_of(name, judgement.MODEL_SDKS) for name in imports] == [
        "@anthropic-ai/sdk",
        "@langchain",
        "openai",
        "ai",
        "@ai-sdk",
        "@google/genai",
        "@google/generative-ai",
        "@mistralai/mistralai",
        "cohere-ai",
        "langchain",
        "",
        "",
        "",
    ]
    model = Model(
        canvas=(800, 600),
        containers=(),
        regions=(),
        components=(Component(id="Users", does="d", implemented_by=("app.user",)),),
        flows=(),
        flow_kinds=(),
    )
    facts = {"components": {"app.user": {"external": ["@anthropic-ai/sdk", "@langchain/openai"]}}}
    assert judgement.model_sdk_imports(model, facts) == [
        "model sdk: module app.user imports @anthropic-ai/sdk and its component Users is not an agent",
        "model sdk: module app.user imports @langchain and its component Users is not an agent",
    ]
