"""Tests for the second Codex review of the TypeScript adapter.

Each test name gives the result ID (ts-adapter-N). Each TypeScript test failed on
`origin/main` at 13a7f45. The Python test also passed there: the repair keeps that result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import write_tree

from systemap import check, config, extract, live_watch
from systemap.model import Component
from systemap.typescript import parse_surface
from systemap.typescript import test_names as names_of_tests
from systemap.typescript_config_files import (
    typescript_config_paths,
    typescript_extraction_inputs,
)
from systemap.typescript_repo import TYPESCRIPT_REPOSITORY

ROOTS = 'language = "typescript"\n[package_roots]\n"src" = "app"\n'


def build(root: Path, files: dict[str, str], roots: str = ROOTS) -> dict[str, Any]:
    write_tree(root, {"systemap.toml": roots, "tsconfig.json": "{}", **files})
    return extract.build(config.load(root))


def surface(source: str) -> dict[str, Any]:
    found = parse_surface(source, "src/m.ts")
    assert found is not None
    return found


def test_ts_adapter_1_nul_import_is_an_unresolved_local_import(tmp_path: Path) -> None:
    """Acceptance: a NUL character in an import path gives an unresolved local import.
    The extraction does not stop. The same is true for a test file, an alias, a subpath
    import, and a program dependency.
    """
    facts = build(
        tmp_path,
        {
            "tsconfig.json": json.dumps(
                {"files": ["src/index.ts"], "compilerOptions": {"paths": {"@/*": ["./src/*"]}}}
            ),
            "package.json": json.dumps({"name": "app", "imports": {"#*": "./src/*"}}),
            "src/index.ts": (
                'export const load = () => import("./\\0");\n'
                'export const alias = () => import("@/\\0");\n'
                'export const sub = () => import("#\\0");\n'
            ),
            "src/index.test.ts": 'import "./\\0";\nit("loads", () => {});\n',
        },
    )
    unresolved = facts["components"]["app.index"]["completeness"]["unresolved_imports"]
    assert unresolved == ["#\x00", "./\x00", "@/\x00"]


def test_ts_adapter_2_comment_before_the_first_argument(tmp_path: Path) -> None:
    """Acceptance: a comment before the first argument of `import()`, `require()`, and a
    test call does not remove the import or the test.
    """
    facts = build(
        tmp_path,
        {
            "src/index.ts": (
                'export const load = () => import(/* webpackChunkName: "service" */ "./service");\n'
                'export const need = () => require(/* c */ "./other");\n'
            ),
            "src/service.ts": "export const a = 1;\n",
            "src/other.ts": "export const b = 1;\n",
        },
    )
    assert facts["components"]["app.index"]["imports"] == ["app.other", "app.service"]
    assert names_of_tests(
        'describe(/* s */ "suite", () => { it(/* c */ "save", () => {}); });'
    ) == ["suite > save"]


def test_ts_adapter_3_default_export_of_a_local_class(tmp_path: Path) -> None:
    """Acceptance: `export default Store` gives the class record of `Store`, as
    `export default class Store` does. `check` accepts the interface `default.get()` for
    the two forms.
    """
    direct = surface("export default class Store { get(): number { return 1; } }")
    local = surface("class Store { get(): number { return 1; } }\nexport default Store;\n")
    assert (
        local["classes"] == direct["classes"] == [{"name": "Store", "methods": ["get(): number"]}]
    )
    for source in (
        "export default class Store { get(): number { return 1; } }\n",
        "class Store { get(): number { return 1; } }\nexport default Store;\n",
    ):
        root = tmp_path / str(len(source))
        facts = build(root, {"src/store.ts": source})
        component = Component(
            id="Store", does="d", interface="default.get()", implemented_by=("app.store",)
        )
        assert check.interface_problem(component, facts["components"]) == ""


def test_ts_adapter_4_root_name_is_not_an_npm_identity(tmp_path: Path) -> None:
    """Acceptance: without package `exports`, `import "app"` and `import "app/util"` are
    external imports. They do not resolve to `app.index` or `app.util`.
    """
    facts = build(
        tmp_path,
        {
            "package.json": '{"name":"app"}',
            "src/index.ts": "export const a = 1;\n",
            "src/util.ts": "export const u = 1;\n",
            "src/main.ts": 'import "app";\nimport { u } from "app/util";\nexport const m = u;\n',
        },
    )
    main = facts["components"]["app.main"]
    assert main["imports"] == []
    assert main["completeness"]["unresolved_imports"] == []
    assert main["external"] == ["app", "app/util"]


def test_ts_adapter_5_alias_uses_the_first_existing_target(tmp_path: Path) -> None:
    """Acceptance: the alias `@helper` names `shared/helper.ts`, the first existing
    target. That file has no module, so the import is unresolved. It is not `app.helper`.
    """
    facts = build(
        tmp_path,
        {
            "tsconfig.json": json.dumps(
                {
                    "compilerOptions": {
                        "paths": {"@helper": ["./shared/helper.ts", "./src/helper.ts"]}
                    }
                }
            ),
            "shared/helper.ts": "export const h = 1;\n",
            "src/helper.ts": "export const h = 2;\n",
            "src/main.ts": 'import { h } from "@helper";\nexport const m = h;\n',
        },
    )
    main = facts["components"]["app.main"]
    assert main["imports"] == []
    assert main["completeness"]["unresolved_imports"] == ["@helper"]


def test_ts_adapter_6_project_discovery_follows_package_imports(tmp_path: Path) -> None:
    """Acceptance: `helper.ts` is in the app program through `#helper`. Thus it uses the
    alias `@lib/*` of the app project: it imports `app.lib.log` and has no external import.
    """
    facts = build(
        tmp_path,
        {
            "tsconfig.json": json.dumps(
                {"files": [], "references": [{"path": "./tsconfig.app.json"}]}
            ),
            "tsconfig.app.json": json.dumps(
                {
                    "files": ["src/main.ts"],
                    "compilerOptions": {"paths": {"@lib/*": ["./src/lib/*"]}},
                }
            ),
            "package.json": json.dumps({"name": "web", "imports": {"#helper": "./src/helper.ts"}}),
            "src/main.ts": 'import { h } from "#helper";\nexport const m = h;\n',
            "src/helper.ts": 'import { log } from "@lib/log";\nexport const h = log;\n',
            "src/lib/log.ts": "export const log = 1;\n",
        },
    )
    helper = facts["components"]["app.helper"]
    assert facts["components"]["app.main"]["imports"] == ["app.helper"]
    assert helper["imports"] == ["app.lib.log"]
    assert helper["external"] == []


def test_ts_adapter_7_nested_project_without_root_config_has_the_version(
    tmp_path: Path,
) -> None:
    """Acceptance: with TypeScript 5.9.3 installed and no root tsconfig.json, the bin
    target `dist/cli.js` gives `cli.cli`, and `dist/src/cli.js` is an entry issue.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"cli/src" = "cli"\n',
            "node_modules/typescript/package.json": '{"name":"typescript","version":"5.9.3"}',
            "cli/tsconfig.json": json.dumps(
                {"include": ["src"], "compilerOptions": {"outDir": "dist"}}
            ),
            "cli/package.json": json.dumps(
                {"name": "cli", "bin": {"good": "./dist/cli.js", "bad": "./dist/src/cli.js"}}
            ),
            "cli/src/cli.ts": "export const run = 1;\n",
        },
    )
    facts = extract.build(config.load(tmp_path))
    bins = {p["name"]: p["module"] for p in facts["entry_points"] if p["kind"] == "console_script"}
    assert bins == {"good": "cli.cli"}
    assert [issue["name"] for issue in facts["entry_point_issues"]] == ["bad"]


def test_ts_adapter_8_second_parse_keeps_string_literals() -> None:
    """Acceptance: a module that uses the second parse keeps the literal `"<in T>"` in
    its constant value and its API fingerprint. A variance keyword still parses.
    """
    found = surface(
        'export type * from "./types";\n'
        'export const TEXT = "<in T>";\n'
        "export const NOTE = `<out T>`;\n"
        "export interface Box<in out T> { value: T }\n"
    )
    values = {entry["name"]: entry["value"] for entry in found["constants"]}
    assert values == {"TEXT": '"<in T>"', "NOTE": "`<out T>`"}
    api = {entry["name"]: entry["fingerprint"] for entry in found["api"]}
    assert "<in T>" in api["TEXT"]
    assert "<out T>" in api["NOTE"]
    assert [entry["name"] for entry in found["types"]] == ["Box"]


def test_ts_adapter_9_binding_default_is_not_a_public_name() -> None:
    """Acceptance: `export const { value = fallback } = input` gives only `value`."""
    found = surface(
        "const fallback = 1;\nconst input: { value?: number } = {};\n"
        "export const { value = fallback } = input;\n"
    )
    assert [entry["name"] for entry in found["names"]] == ["value"]
    assert [entry["name"] for entry in found["api"]] == ["value"]


def test_ts_adapter_10_local_exports_of_types_are_types() -> None:
    """Acceptance: `export { Shape, Alias, Color, Store }` gives three `types` records with
    their categories and one `classes` record, as direct exports do.
    """
    local = surface(
        "interface Shape { id: string }\ntype Alias = number;\nenum Color { Red }\n"
        "class Store {}\nexport { Shape, Alias, Color, Store };\n"
    )
    direct = surface(
        "export interface Shape { id: string }\nexport type Alias = number;\n"
        "export enum Color { Red }\nexport class Store {}\n"
    )
    assert local["types"] == direct["types"]
    assert [(t["name"], t["category"]) for t in local["types"]] == [
        ("Shape", "interface"),
        ("Alias", "type_alias"),
        ("Color", "enum"),
    ]
    assert local["classes"] == direct["classes"] == [{"name": "Store", "methods": []}]
    renamed = surface("interface Shape { id: string }\nexport { Shape as Form };\n")
    assert renamed["classes"] == []
    assert [(t["name"], t["category"]) for t in renamed["types"]] == [("Form", "interface")]


def test_ts_adapter_11_a_hidden_import_name_is_not_a_use(tmp_path: Path) -> None:
    """Acceptance: a parameter, a local variable, or a catch parameter that hides the
    imported name `total` gives no use. Only the call on line 9 is a use.
    """
    facts = build(
        tmp_path,
        {
            "src/ledger.ts": "export function total(): number { return 1; }\n",
            "src/relay.ts": (
                'import { total } from "./ledger";\n'
                "export function relay(total: () => number) { return total(); }\n"
                "export function inner() {\n"
                "  const total = () => 2;\n"
                "  return total();\n"
                "}\n"
                "export const arrow = (total: () => number) => total();\n"
                "export function guarded() { try { return 0; } catch (total) { return total; } }\n"
                "export function sum() { return total(); }\n"
            ),
        },
    )
    sites = facts["components"]["app.relay"]["call_sites"]
    assert [(s["local"], [use[0] for use in s["uses"]]) for s in sites] == [("total", [9])]


def test_ts_adapter_11_value_bindings_keep_their_own_scope(tmp_path: Path) -> None:
    """Acceptance: a value binding in a block keeps its use in that block (line 4). A
    parameter that hides a value binding of the module is a different binding: the module
    binding of line 6 has only the use on line 7, and the parameter has the use on line 8.
    """
    facts = build(
        tmp_path,
        {
            "src/ledger.ts": "export class Ledger { run(): number { return 1; } }\n",
            "src/user.ts": (
                'import { Ledger } from "./ledger";\n'
                "export function local(flag: boolean) {\n"
                "  if (flag) { const book = new Ledger();\n"
                "    return book.run(); }\n"
                "}\n"
                "const shared = new Ledger();\n"
                "export function first() { return shared.run(); }\n"
                "export function other(shared: Ledger) { return shared.run(); }\n"
            ),
        },
    )
    sites = facts["components"]["app.user"]["call_sites"]
    uses = {(s["local"], s["line"]): [use[0] for use in s["uses"]] for s in sites}
    assert uses[("book", 3)] == [4]
    assert uses[("shared", 6)] == [7]
    assert uses[("shared", 8)] == [8]


def test_ts_adapter_12_test_identities_are_unique() -> None:
    """Acceptance: the tests `save`, `save`, and `save #2` give three different identities."""
    names = names_of_tests(
        'it("save", () => {});\nit("save", () => {});\nit("save #2", () => {});\n'
    )
    assert len(names) == 3
    assert len(set(names)) == 3
    assert names[0] == "save"
    assert names[2] == "save #2"


def test_ts_adapter_13_quoted_method_name_is_a_method(tmp_path: Path) -> None:
    """Acceptance: the method reader gives `get` for the quoted names `"get"`, `'get'`, and
    `"g\\u0065t"`. `check` accepts the interface `Store.get()`.
    """
    for header in ('"get"(): number', "'get'(): number", '"g\\u0065t"(): number'):
        assert TYPESCRIPT_REPOSITORY.method_name(header) == "get"
    assert TYPESCRIPT_REPOSITORY.method_name('"get value"(): number') == ""
    facts = build(
        tmp_path, {"src/store.ts": 'export class Store { "get"(): number { return 1; } }\n'}
    )
    component = Component(
        id="Store", does="d", interface="Store.get()", implemented_by=("app.store",)
    )
    assert check.interface_problem(component, facts["components"]) == ""


def test_ts_adapter_14_output_folder_names_are_source_folders(tmp_path: Path) -> None:
    """Acceptance: configuration discovery, the input digest, and the watcher include
    `src/build/tsconfig.json` and `src/dist/a.ts`, because extraction reads them.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/build/tsconfig.json": json.dumps(
                {"compilerOptions": {"paths": {"@x": ["./x.ts"]}}}
            ),
            "src/build/x.ts": "export const x = 1;\n",
            "src/build/main.ts": 'import { x } from "@x";\nexport const m = x;\n',
            "src/dist/a.ts": "export const a = 1;\n",
        },
    )
    nested = tmp_path / "src" / "build" / "tsconfig.json"
    assert nested in typescript_config_paths(tmp_path, [tmp_path / "src"])
    assert nested in typescript_extraction_inputs(tmp_path, [tmp_path / "src"])
    watched = live_watch.watched(tmp_path)
    assert nested in watched
    assert tmp_path / "src" / "dist" / "a.ts" in watched
    facts = extract.build(config.load(tmp_path))
    assert facts["components"]["app.build.main"]["imports"] == ["app.build.x"]
    assert "app.dist.a" in facts["components"]


def test_ts_adapter_14_python_watcher_agrees_with_extraction(tmp_path: Path) -> None:
    """Acceptance: for Python, the watcher includes a source file in a folder with the
    name `build` exactly when extraction gives its module.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "python"\n[package_roots]\n"pkg" = "pkg"\n',
            "pkg/__init__.py": '"""A package."""\n',
            "pkg/build/__init__.py": '"""A folder with an output name."""\n',
            "pkg/build/m.py": '"""A module."""\n',
        },
    )
    facts = extract.build(config.load(tmp_path))
    watched = tmp_path / "pkg" / "build" / "m.py" in live_watch.watched(tmp_path)
    assert watched == ("pkg.build.m" in facts["components"])
