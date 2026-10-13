"""Tests for the TypeScript module resolution, the project selection, and the source reads.

Each test gives the result that tsc 5.9.3 gives for the same layout. The handbook page
for the module rules is https://www.typescriptlang.org/docs/handbook/modules/reference.html.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, extract
from systemap.config import ConfigError
from systemap.typescript import TYPESCRIPT
from systemap.typescript import test_names as names_of_tests

ROOTS = 'language = "typescript"\n[package_roots]\n"src" = "web"\n'


def build(root: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(root, tree)
    return extract.build(config.load(root))


def test_failed_relative_import_is_not_a_dotted_name_guess(tmp_path: Path) -> None:
    """Acceptance: `./c` in src/a.b.ts does not resolve, because src/c.ts is absent.

    The module id of src/a.b.ts is `web.a.b`, and src/a/c.ts has the id `web.a.c`. tsc
    resolves `./c` relative to the folder of the importing file, so it reports TS2307.
    The import must have no target and must be an unresolved local import.
    """
    facts = build(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/a.b.ts": 'import { c } from "./c";\nexport const x = c;\n',
            "src/a/c.ts": "export const c = 1;\n",
        },
    )
    record = facts["components"]["web.a.b"]
    assert record["uses"] == {}
    assert record["completeness"]["unresolved_imports"] == ["./c"]


@pytest.mark.parametrize(
    ("target", "specifier", "resolves"),
    [
        ("mod.ts", "./mod.mjs", False),
        ("mod.ts", "./mod.cjs", False),
        ("mod.mts", "./mod.js", False),
        ("mod.mts", "./mod", False),
        ("mod.cts", "./mod", False),
        ("mod.mts", "./mod.mjs", True),
        ("mod.cts", "./mod.cjs", True),
        ("mod.ts", "./mod.js", True),
        ("mod.tsx", "./mod.js", True),
        ("mod.ts", "./mod.jsx", True),
        ("mod.ts", "./mod", True),
    ],
)
def test_import_extension_family_selects_the_source_extension(
    tmp_path: Path, target: str, specifier: str, resolves: bool
) -> None:
    """Acceptance: each case gives the tsc 5.9.3 result with `bundler` and `node16`.

    The handbook section "File extension substitution" gives the rule: `.js` and `.jsx`
    select `.ts` and `.tsx`, `.mjs` selects `.mts`, and `.cjs` selects `.cts`. An import
    without an extension selects `.ts` and `.tsx` only. The measurement used
    `tsc --noEmit --moduleResolution bundler` and `--moduleResolution node16`.
    """
    facts = build(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            f"src/{target}": "export const x = 1;\n",
            "src/main.ts": f'import {{ x }} from "{specifier}";\nexport const y = x;\n',
        },
    )
    record = facts["components"]["web.main"]
    assert record["uses"] == ({"web.mod": ["x"]} if resolves else {})
    assert record["completeness"]["unresolved_imports"] == ([] if resolves else [specifier])


def test_jsx_import_selects_tsx_before_ts(tmp_path: Path) -> None:
    """Acceptance: `./mod.jsx` gives mod.tsx, and `./mod.js` gives mod.ts.

    `tsc --traceResolution` (5.9.3) gave these files when both mod.ts and mod.tsx exist.
    The two files have different module ids here, so the test can see the selection.
    """
    facts = build(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/a/mod.ts": "export const x = 1;\n",
            "src/b/mod.tsx": "export const x = 2;\n",
            "src/a/main.ts": 'import { x } from "./mod.jsx";\nexport const y = x;\n',
            "src/b/main.ts": 'import { x } from "./mod.js";\nexport const y = x;\n',
        },
    )
    assert facts["components"]["web.a.main"]["uses"] == {"web.a.mod": ["x"]}
    assert facts["components"]["web.b.main"]["uses"] == {"web.b.mod": ["x"]}


def test_package_bin_mjs_target_maps_to_the_mts_source(tmp_path: Path) -> None:
    """Acceptance: the bin target dist/cli.mjs maps to src/cli.mts and not to src/cli.ts.

    tsc emits a `.mts` file as `.mjs`. A `.ts` file gives `.js`, never `.mjs`.
    """
    facts = build(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "package.json": json.dumps(
                {"name": "web", "bin": {"good": "./dist/cli.mjs", "bad": "./dist/tool.mjs"}}
            ),
            "tsconfig.json": '{"compilerOptions":{"rootDir":"src","outDir":"dist"}}',
            "src/cli.mts": "export function main(): void {}\n",
            "src/tool.ts": "export function main(): void {}\n",
        },
    )
    scripts = {
        p["name"]: p["module"] for p in facts["entry_points"] if p["kind"] == "console_script"
    }
    assert scripts == {"good": "web.cli"}
    assert [issue["name"] for issue in facts["entry_point_issues"]] == ["bad"]


def test_include_pattern_outside_the_config_directory_selects_inputs(tmp_path: Path) -> None:
    """Acceptance: config/tsconfig.app.json with `"include": ["../src/**/*.ts"]` compiles
    src/main.ts, so its `paths` alias resolves.

    `tsc -p config/tsconfig.app.json --listFilesOnly` (5.9.3) lists src/main.ts and
    src/lib/h.ts. The handbook (tsconfig reference, `include`) resolves the patterns
    relative to the directory of the tsconfig file that declares them.
    """
    facts = build(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": json.dumps(
                {"files": [], "references": [{"path": "./config/tsconfig.app.json"}]}
            ),
            "config/tsconfig.app.json": json.dumps(
                {
                    "compilerOptions": {"paths": {"@lib/*": ["../src/lib/*"]}},
                    "include": ["../src/**/*.ts"],
                }
            ),
            "src/main.ts": 'import { h } from "@lib/h";\nexport const m = h;\n',
            "src/lib/h.ts": "export const h = 1;\n",
        },
    )
    assert facts["components"]["web.main"]["uses"] == {"web.lib.h": ["h"]}
    assert facts["components"]["web.main"]["external"] == []


def test_include_pattern_outside_the_repository_selects_no_file(tmp_path: Path) -> None:
    """Acceptance: an include pattern that leaves the repository selects no file there.

    The extractor reads only files in the repository. The repository is a subfolder,
    and a source file is in its parent folder.
    """
    repo = tmp_path / "repo"
    write_tree(tmp_path, {"outside/other.ts": "export const o = 1;\n"})
    facts = build(
        repo,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": json.dumps({"include": ["src", "../outside/**/*.ts"]}),
            "src/main.ts": "export const m = 1;\n",
        },
    )
    assert sorted(facts["components"]) == ["web.main"]


def test_project_inventory_includes_imported_dependencies(tmp_path: Path) -> None:
    """Acceptance: src/helper.ts uses the `#lib/*` alias of tsconfig.app.json.

    tsconfig.app.json has `"files": ["src/main.ts"]`, and src/main.ts imports
    src/helper.ts. `tsc -p tsconfig.app.json --listFilesOnly` (5.9.3) lists
    src/helper.ts and src/lib/log.ts, so that project compiles them with its aliases.
    The handbook (tsconfig reference, `files`) says that the compiler also includes
    the files that the selected files import.
    """
    facts = build(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": json.dumps(
                {"files": [], "references": [{"path": "./tsconfig.app.json"}]}
            ),
            "tsconfig.app.json": json.dumps(
                {
                    "compilerOptions": {"paths": {"#lib/*": ["./src/lib/*"]}},
                    "files": ["src/main.ts"],
                }
            ),
            "src/main.ts": 'import { help } from "./helper";\nexport const m = help;\n',
            "src/helper.ts": 'import { log } from "#lib/log";\nexport const help = log;\n',
            "src/lib/log.ts": "export const log = 1;\n",
        },
    )
    helper = facts["components"]["web.helper"]
    assert helper["uses"] == {"web.lib.log": ["log"]}
    assert helper["completeness"]["unresolved_imports"] == []


def test_nested_package_root_includes_imported_dependencies(tmp_path: Path) -> None:
    """Acceptance: with TypeScript 5, the bin target dist/src/main.js resolves to
    packages/cli/src/main.ts.

    packages/cli/tsconfig.json includes `src`, and src/main.ts imports ../shared.ts.
    `tsc -p packages/cli` (5.9.3) emits dist/src/main.js and dist/shared.js, because the
    common source folder of the program files is packages/cli.
    """
    facts = build(
        tmp_path,
        {
            "systemap.toml": ('language = "typescript"\n[package_roots]\n"packages/cli" = "cli"\n'),
            "package.json": '{"name":"mono","private":true}',
            "tsconfig.json": '{"files":[]}',
            "node_modules/typescript/package.json": '{"name":"typescript","version":"5.9.3"}',
            "packages/cli/package.json": json.dumps(
                {"name": "cli", "bin": {"cli": "./dist/src/main.js"}}
            ),
            "packages/cli/tsconfig.json": '{"compilerOptions":{"outDir":"dist"},"include":["src"]}',
            "packages/cli/src/main.ts": (
                'import { shared } from "../shared";\nexport function main(): void { shared(); }\n'
            ),
            "packages/cli/shared.ts": "export function shared(): void {}\n",
        },
    )
    scripts = [p for p in facts["entry_points"] if p["kind"] == "console_script"]
    assert [(p["name"], p["module"]) for p in scripts] == [("cli", "cli.src.main")]
    assert facts["entry_point_issues"] == []


def test_test_identities_include_the_enclosing_suites() -> None:
    """Acceptance: two suites with the same test name give two test identities.

    A test name with the same suite path as an earlier test gets the suffix `#2`, `#3`,
    and so on. Thus a removed duplicate test changes the identities.
    """
    assert names_of_tests(
        'describe("one", () => { it("works", () => {}); });\n'
        'describe("two", () => { it("works", () => {}); });\n'
        'describe.each([[1]])("table %i", () => { describe("inner", () => { test("a", () => {}); }); });\n'
        'test("top", () => {}); test("top", () => {});\n'
        'describe(Store.name, () => { it("saves", () => {}); });\n'
    ) == [
        "one > works",
        "two > works",
        "table %i > inner > a",
        "top",
        "top #2",
        "Store.name > saves",
    ]


def test_two_suites_give_two_test_facts(tmp_path: Path) -> None:
    """Acceptance: the module record has two tests, and the digest changes if one goes."""
    tree = {
        "systemap.toml": 'language = "typescript"\ntests_dir = "tests"\n'
        '[package_roots]\n"src" = "web"\n',
        "tsconfig.json": "{}",
        "src/service.ts": "export function serve(): void {}\n",
        "tests/service.test.ts": (
            'import { serve } from "../src/service";\n'
            'describe("one", () => { it("works", () => serve()); });\n'
            'describe("two", () => { it("works", () => serve()); });\n'
        ),
    }
    first = build(tmp_path, tree)["components"]["web.service"]
    assert first["tests"] == [
        "tests/service.test.ts::one > works",
        "tests/service.test.ts::two > works",
    ]
    tree["tests/service.test.ts"] = (
        'import { serve } from "../src/service";\n'
        'describe("one", () => { it("works", () => serve()); });\n'
    )
    second = build(tmp_path, tree)["components"]["web.service"]
    assert second["tests_digest"] != first["tests_digest"]


@pytest.fixture
def unreadable(tmp_path: Path) -> Iterator[Path]:
    """Give a function that removes read permission from a file, and restores it later."""
    changed: list[Path] = []

    def remove(path: Path) -> Path:
        path.chmod(0)
        changed.append(path)
        return path

    yield remove  # type: ignore[misc]
    for path in changed:
        path.chmod(0o644)


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs file permissions")
@pytest.mark.parametrize(
    ("tree", "module"),
    [
        (
            {
                "systemap.toml": ROOTS,
                "tsconfig.json": "{}",
                "src/locked.ts": "export const x = 1;\n",
            },
            "web.locked",
        ),
        (
            {
                "systemap.toml": 'language = "python"\n[package_roots]\n"pkg" = "pkg"\n',
                "pkg/__init__.py": "",
                "pkg/locked.py": "X = 1\n",
            },
            "pkg.locked",
        ),
    ],
    ids=["typescript", "python"],
)
def test_unreadable_source_keeps_a_not_known_module_record(
    tmp_path: Path, unreadable: Any, tree: dict[str, str], module: str
) -> None:
    """Acceptance: a source file that raises PermissionError keeps its module record.

    The record has `completeness.parsed` false and a read reason. The module must not
    leave the facts without a record.
    """
    write_tree(tmp_path, tree)
    unreadable(tmp_path / next(path for path in tree if "locked" in path))
    facts = extract.build(config.load(tmp_path))
    record = facts["components"][module]
    assert record["completeness"]["parsed"] is False
    assert record["completeness"]["reason"] == "source could not be read: PermissionError"
    assert record["completeness"]["unresolved_imports"] is None


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs file permissions")
def test_unreadable_test_file_gives_a_test_file_issue(tmp_path: Path, unreadable: Any) -> None:
    """Acceptance: a test file that raises PermissionError gives one test file issue."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\ntests_dir = "tests"\n'
            '[package_roots]\n"src" = "web"\n',
            "tsconfig.json": "{}",
            "src/service.ts": "export function serve(): void {}\n",
            "tests/service.test.ts": 'import { serve } from "../src/service";\n',
        },
    )
    unreadable(tmp_path / "tests/service.test.ts")
    facts = extract.build(config.load(tmp_path))
    assert facts["test_file_issues"] == [
        {
            "file": "tests/service.test.ts",
            "problem": {
                "line": 0,
                "reason": "source could not be read: PermissionError",
                "source": "",
                "cause": "read",
            },
        }
    ]


@pytest.mark.parametrize("text", ['{"bin":', "[1, 2]"])
def test_incorrect_package_json_is_a_configuration_error(tmp_path: Path, text: str) -> None:
    """Acceptance: a package.json file that does not parse to an object stops extraction.

    A missing package.json file is not an error. npm also refuses such a file.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": ROOTS,
            "tsconfig.json": "{}",
            "src/main.ts": "export const m = 1;\n",
        },
    )
    extract.build(config.load(tmp_path))
    (tmp_path / "package.json").write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="package.json"):
        extract.build(config.load(tmp_path))


def test_incorrect_nested_package_json_is_a_configuration_error(tmp_path: Path) -> None:
    """Acceptance: an incorrect package.json file of a package folder stops extraction."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"packages/web" = "web"\n',
            "packages/web/package.json": '{"bin":',
            "packages/web/tsconfig.json": "{}",
            "packages/web/main.ts": "export const m = 1;\n",
        },
    )
    with pytest.raises(ConfigError, match="packages/web/package.json"):
        extract.build(config.load(tmp_path))


def test_source_discovery_does_not_enter_node_modules(tmp_path: Path) -> None:
    """Acceptance: `source_paths` lists no folder below node_modules in a package root.

    An audit hook records each folder that `os.scandir` and `os.listdir` open. The
    extraction-time measurement is in `bench/typescript_discovery.py`: with 40,000 files
    in node_modules, `extract.build` must take at most 1.2 times the time without them.
    """
    write_tree(
        tmp_path,
        {
            "src/main.ts": "export const m = 1;\n",
            "node_modules/pkg/lib/index.ts": "export const x = 1;\n",
            "node_modules/pkg/deep/more/index.ts": "export const x = 1;\n",
        },
    )
    opened: list[str] = []
    active = [True]

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if active[0] and event in ("os.scandir", "os.listdir") and args:
            opened.append(os.fspath(args[0]) if args[0] is not None else "")

    sys.addaudithook(hook)
    try:
        found = list(TYPESCRIPT.source_paths(tmp_path, tmp_path, (), ()))
    finally:
        active[0] = False
    assert found == [tmp_path / "src" / "main.ts"]
    assert opened and not [path for path in opened if "node_modules" in Path(path).parts]
