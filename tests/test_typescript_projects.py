"""Tests for the tsconfig projects, the module resolution and the package entries of the
TypeScript adapter. Each test gives the result that tsc gives for the same layout.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, extract, typescript_config
from systemap.cli import main

ROOTS = 'language = "typescript"\n[package_roots]\n"src" = "web"\n'


def build(root: Path) -> dict[str, Any]:
    return extract.build(config.load(root))


def test_solution_tsconfig_references_give_the_path_aliases(tmp_path: Path) -> None:
    """Acceptance: the `npm create vite` react-ts layout resolves `@/` imports to source.

    `tsc -p tsconfig.app.json --traceResolution` resolves `@/lib/utils` to
    src/lib/utils.ts. The top-level tsconfig.json has `"files": []`.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "package.json": '{"name":"web"}',
            "tsconfig.json": json.dumps(
                {
                    "files": [],
                    "references": [
                        {"path": "./tsconfig.app.json"},
                        {"path": "./tsconfig.node.json"},
                    ],
                }
            ),
            "tsconfig.app.json": json.dumps(
                {
                    "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}},
                    "include": ["src"],
                }
            ),
            "tsconfig.node.json": '{"include": ["vite.config.ts"]}',
            "src/App.tsx": (
                'import { Button } from "@/components/Button";\n'
                "export default function App() { return Button(); }\n"
            ),
            "src/components/Button.tsx": (
                'import { cn } from "@/lib/utils";\nexport function Button() { return cn(); }\n'
            ),
            "src/lib/utils.ts": "export function cn(): string { return ''; }\n",
        },
    )
    components = build(tmp_path)["components"]
    assert components["web.App"]["uses"] == {"web.components.Button": ["Button"]}
    assert components["web.components.Button"]["uses"] == {"web.lib.utils": ["cn"]}
    assert components["web.App"]["external"] == []
    assert components["web.components.Button"]["external"] == []


MONOREPO = {
    "systemap.toml": (
        'language = "typescript"\n[package_roots]\n'
        '"packages/core/src" = "mono.core"\n"packages/api/src" = "mono.api"\n'
    ),
    "package.json": '{"name":"mono","private":true,"workspaces":["packages/*"]}',
    "tsconfig.base.json": '{"compilerOptions":{"strict":true}}',
    "packages/core/package.json": '{"name":"@mono/core","exports":{".":"./dist/index.js"}}',
    "packages/core/tsconfig.json": (
        '{"extends":"../../tsconfig.base.json","compilerOptions":{"rootDir":"src","outDir":"dist"}}'
    ),
    "packages/core/src/index.ts": 'export { hash } from "./hash";\n',
    "packages/core/src/hash.ts": "export function hash(): string { return ''; }\n",
    "packages/api/package.json": (
        '{"name":"@mono/api","bin":{"api":"./dist/main.js","broken":"./dist/missing.js"}}'
    ),
    "packages/api/tsconfig.json": (
        '{"extends":"../../tsconfig.base.json","compilerOptions":{"rootDir":"src",'
        '"outDir":"dist","paths":{"#lib/*":["./src/lib/*"]}},"references":[{"path":"../core"}]}'
    ),
    "packages/api/src/main.ts": (
        'import { hash } from "@mono/core";\nimport { log } from "#lib/log";\n'
        "export function main(): void { log(hash()); }\n"
    ),
    "packages/api/src/lib/log.ts": "export function log(text: string): void { void text; }\n",
}


@pytest.mark.parametrize("solution", [True, False])
def test_monorepo_packages_give_their_own_tsconfig_and_bin(tmp_path: Path, solution: bool) -> None:
    """Acceptance: each package uses its own tsconfig.json paths and package.json bin.

    `solution` adds a top-level tsconfig.json with `references` to both packages.
    Without it, the nearest tsconfig.json above each file gives the project.
    """
    tree = dict(MONOREPO)
    if solution:
        tree["tsconfig.json"] = (
            '{"files":[],"references":[{"path":"./packages/core"},{"path":"./packages/api"}]}'
        )
    write_tree(tmp_path, tree)
    facts = build(tmp_path)
    main = facts["components"]["mono.api.main"]
    assert main["uses"] == {"mono.api.lib.log": ["log"], "mono.core.index": ["hash"]}
    assert main["external"] == []
    assert {
        "kind": "console_script",
        "name": "api",
        "module": "mono.api.main",
        "target": "",
        "same_as": "",
        "symbol": "",
        "label": "api (console script)",
    } in (facts["entry_points"])
    assert facts["entry_point_issues"] == [
        {
            "kind": "package_bin",
            "name": "broken",
            "target": "packages/api/dist/missing.js",
            "reason": (
                "The parser could not resolve the package.json bin target to a TypeScript module."
            ),
            "cause": "target",
        }
    ]


@pytest.mark.parametrize("folder", [".", "config"])
def test_extends_without_json_suffix_reads_the_named_file(tmp_path: Path, folder: str) -> None:
    """Acceptance: `"extends": "./tsconfig.base"` reads tsconfig.base.json, as tsc does.

    In the folder `config`, a different tsconfig.json must not be read instead.
    """
    prefix = "" if folder == "." else f"{folder}/"
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "app"\n',
            "tsconfig.json": json.dumps({"extends": f"./{prefix}tsconfig.base"}),
            f"{prefix}tsconfig.base.json": json.dumps(
                {"compilerOptions": {"baseUrl": "..", "paths": {"@core/*": ["src/core/*"]}}}
                if prefix
                else {"compilerOptions": {"paths": {"@core/*": ["./src/core/*"]}}}
            ),
            "config/tsconfig.json": (
                '{"compilerOptions":{"baseUrl":"..","paths":{"@core/*":["src/wrong/*"]}}}'
            ),
            "src/index.ts": 'import { core } from "@core/a";\nexport function run(): void { core(); }\n',
            "src/core/a.ts": "export function core(): void {}\n",
        },
    )
    index = build(tmp_path)["components"]["app.index"]
    assert index["uses"] == {"app.core.a": ["core"]}
    assert index["external"] == []


def test_bare_import_without_base_url_is_a_package(tmp_path: Path) -> None:
    """Acceptance: without `baseUrl`, `import config from "config"` does not resolve to
    config.ts in the project folder. tsc resolves it in node_modules.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"." = "svc"\n',
            "tsconfig.json": '{"compilerOptions":{"module":"commonjs"}}',
            "config.ts": "export const PORT = 1;\n",
            "events.ts": "export function publish(): void {}\n",
            "server.ts": (
                'import config from "config";\nimport { EventEmitter } from "events";\n'
                'import { PORT } from "./config";\n'
                "export function start(): number { void config; void EventEmitter; return PORT; }\n"
            ),
        },
    )
    server = build(tmp_path)["components"]["svc.server"]
    assert server["uses"] == {"svc.config": ["PORT"]}
    assert "config" in server["external"]


def test_mts_and_cts_files_are_modules(tmp_path: Path) -> None:
    """Acceptance: tsc compiles .mts and .cts files, and `./modern.mjs` names modern.mts.

    A .d.mts declaration file is not a module.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": '{"compilerOptions":{"module":"nodenext"}}',
            "src/modern.mts": "export function modern(): number { return 1; }\n",
            "src/common.cts": "export function common(): number { return 2; }\n",
            "src/types.d.mts": "export interface Shape { size: number }\n",
            "src/uses.ts": (
                'import { modern } from "./modern.mjs";\nimport { common } from "./common.cjs";\n'
                "export function uses(): number { return modern() + common(); }\n"
            ),
        },
    )
    components = build(tmp_path)["components"]
    assert sorted(components) == ["web.common", "web.modern", "web.uses"]
    assert components["web.uses"]["uses"] == {"web.common": ["common"], "web.modern": ["modern"]}


def test_extraction_does_not_read_node_modules_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance: extraction lists no folder inside node_modules.

    With 100,000 files in node_modules, `extract.build` took 2.97 to 3.10 s before this
    change. A directory listing is the cost, so the test records the listings.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": '{"include":["src"]}',
            "src/index.ts": "export function run(): void {}\n",
            "src/index.test.ts": 'import { run } from "./index";\ntest("runs", () => run());\n',
            "node_modules/pkg/index.ts": "export const x = 1;\n",
            "node_modules/pkg/deep/x.test.ts": 'test("x", () => {});\n',
        },
    )
    listed: list[str] = []
    real = os.scandir

    def scandir(path: Any = ".") -> Iterator[os.DirEntry[str]]:
        listed.append(os.fspath(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", scandir)
    facts = build(tmp_path)
    assert facts["components"]["web.index"]["tests"] == ["src/index.test.ts::runs"]
    assert listed
    assert not [path for path in listed if "node_modules" in Path(path).parts]


def test_bin_in_out_dir_without_a_tsc_output_is_unresolved(tmp_path: Path) -> None:
    """Acceptance: with TypeScript 6, `outDir` dist and no `rootDir`, tsc writes
    dist/src/cli.js. The bin target dist/cli.js then names no output of src/cli.ts.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "app"\n',
            "package.json": (
                '{"name":"ts6","bin":{"ts6":"dist/cli.js"},'
                '"devDependencies":{"typescript":"^6.0.0"}}'
            ),
            "tsconfig.json": '{"compilerOptions":{"outDir":"dist","module":"commonjs"}}',
            "src/cli.ts": "export function main(): void {}\n",
        },
    )
    facts = build(tmp_path)
    assert [point for point in facts["entry_points"] if point["kind"] == "console_script"] == []
    assert [issue["name"] for issue in facts["entry_point_issues"]] == ["ts6"]


def test_tsconfig_inputs_and_source_paths_use_the_same_skip_rule(tmp_path: Path) -> None:
    """Acceptance: a source directory called build or dist is a tsconfig input, as it is a
    source path. node_modules, .venv and outDir are not inputs.

    With TypeScript 5 and no `rootDir`, the inputs give the common source directory src/.
    Thus tsc writes src/main/cli.ts to out/main/cli.js, and the bin target maps to it.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "app"\n',
            "package.json": (
                '{"name":"tool","bin":{"tool":"out/main/cli.js"},'
                '"devDependencies":{"typescript":"^5.9.3"}}'
            ),
            "tsconfig.json": '{"compilerOptions":{"outDir":"out"}}',
            "src/main/cli.ts": "export function main(): void {}\n",
            "src/build/compile.ts": "export function compile(): void {}\n",
            "src/dist/pack.ts": "export function pack(): void {}\n",
            "node_modules/pkg/index.ts": "export const x = 1;\n",
            ".venv/lib/x.ts": "export const y = 1;\n",
            "out/main/cli.ts": "export const old = 1;\n",
        },
    )
    compiler = typescript_config.load_typescript_config(tmp_path)
    inputs = sorted(
        path.relative_to(tmp_path.resolve()).as_posix()
        for path in typescript_config.input_files(compiler, tmp_path)
    )
    assert inputs == ["src/build/compile.ts", "src/dist/pack.ts", "src/main/cli.ts"]
    facts = build(tmp_path)
    assert sorted(facts["components"]) == ["app.build.compile", "app.dist.pack", "app.main.cli"]
    assert {
        "kind": "console_script",
        "name": "tool",
        "module": "app.main.cli",
        "target": "",
        "same_as": "",
        "symbol": "",
        "label": "tool (console script)",
    } in (facts["entry_points"])


def test_init_refuses_an_ambiguous_python_and_typescript_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/index.ts": "export const app = 1;",
        },
    )
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 2
    assert "The source contains python and typescript files" in capsys.readouterr().err
