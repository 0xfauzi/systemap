"""Trial results for TypeScript imports and parse problems (trial-4, trial-6, trial-16).

A trial operated systemap 4ea3bed on the ky and vite repositories. These fixtures copy
the layouts of those repositories in a few files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import write_tree

from systemap import answer_migrations, config, extract, judgement, source_facts
from systemap.config import Answer

# A package of the ky layout: the source is in src, and package.json gives the output.
SELF_NAME = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"." = "web"\n',
    "package.json": json.dumps(
        {
            "name": "@acme/web-lib",
            "type": "module",
            "exports": {
                ".": {"types": "./dist/index.d.ts", "default": "./dist/index.js"},
                "./extra": "./dist/extra.js",
            },
        }
    ),
    "tsconfig.json": '{"compilerOptions": {"outDir": "dist", "rootDir": "src"}}',
    "src/index.ts": "export function start(): void {}\n",
    "src/extra.ts": "export const extra = 1;\n",
    "checks/uses.ts": (
        'import { start } from "@acme/web-lib";\n'
        'import { extra } from "@acme/web-lib/extra";\n'
        'import { hidden } from "@acme/web-lib/hidden";\n'
        "export const run = () => start() || extra || hidden;\n"
    ),
}


def _build(root: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(root, tree)
    return extract.build(config.load(root))


def test_a_self_name_import_is_an_internal_import(tmp_path: Path) -> None:
    """trial-4. Acceptance: `checks/uses.ts` uses `web.src.index` (`start`) and
    `web.src.extra` (`extra`). `@acme/web-lib/hidden` is not in `exports`, so it is an
    unresolved local import and not an external import. On 4ea3bed, `uses` was empty and
    `external` held the three imports.

    The rule: Node.js "Self-referencing a package using its name"
    (https://nodejs.org/api/packages.html#self-referencing-a-package-using-its-name)
    and TypeScript "package.json "imports" and self-name imports"
    (https://www.typescriptlang.org/docs/handbook/modules/reference.html). The name
    must be the `name` of the nearest package.json, and that file must have `exports`.
    For a package of the local project, TypeScript maps the output path in outDir to
    the input file. The `types` condition comes first in the object, so it gives
    `./dist/index.d.ts`, which maps to `src/index.ts`.
    """
    record = _build(tmp_path, SELF_NAME)["components"]["web.checks.uses"]
    assert record["uses"] == {"web.src.extra": ["extra"], "web.src.index": ["start"]}
    assert record["external"] == []
    assert record["completeness"]["unresolved_imports"] == ["@acme/web-lib/hidden"]


def test_a_package_without_exports_has_no_self_name_import(tmp_path: Path) -> None:
    """trial-4. Acceptance: without `exports`, the import of the package name stays an
    external import. Node.js resolves a self-name only through `exports`
    (PACKAGE_SELF_RESOLVE in
    https://nodejs.org/api/esm.html#resolution-algorithm-specification)."""
    tree = dict(SELF_NAME, **{"package.json": '{"name": "@acme/web-lib"}'})
    tree["checks/uses.ts"] = 'import { start } from "@acme/web-lib";\nexport const r = start;\n'
    record = _build(tmp_path, tree)["components"]["web.checks.uses"]
    assert record["uses"] == {}
    assert record["external"] == ["@acme/web-lib"]


SUBPATH = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": json.dumps(
        {
            "name": "web",
            "imports": {
                "#util": {"types": "./dist/util.d.ts", "default": "./dist/util.js"},
                "#format": {"require": "./dist/cjs.js", "import": "./dist/esm.js"},
                "#internal/*": "./src/internal/*.ts",
                "#types/*": "./types/*.d.ts",
                "#pad": "left-pad",
                "#fs": "fs",
                "#blocked": {"import": None, "default": "./dist/util.js"},
            },
        }
    ),
    "tsconfig.json": '{"compilerOptions": {"outDir": "dist", "rootDir": "src"}}',
    "src/util.ts": "export const u = 1;\n",
    "src/esm.ts": "export const f = 1;\n",
    "src/cjs.ts": "export const f = 2;\n",
    "src/internal/deep.ts": "export const d = 1;\n",
    "types/shapes.d.ts": "export type Shape = string;\n",
    "src/main.ts": (
        'import { u } from "#util";\n'
        'import { f } from "#format";\n'
        'import { d } from "#internal/deep";\n'
        'import type { Shape } from "#types/shapes";\n'
        'import pad from "#pad";\n'
        'import { readFile } from "#fs";\n'
        'import { b } from "#blocked";\n'
        'import { m } from "#missing";\n'
        "export const all: Shape = String([u, f, d, pad, readFile, b, m]);\n"
    ),
    "src/legacy.cts": 'import { f } from "#format";\nexport const g = f;\n',
}


def test_subpath_imports_resolve_to_files_of_the_package(tmp_path: Path) -> None:
    """trial-6. Acceptance for `src/main.ts`: `uses` holds `web.util`, `web.esm`, and
    `web.internal.deep`. `external` holds only `left-pad`. The unresolved local imports
    are `#blocked` and `#missing`. `src/legacy.cts` uses `web.cjs`.
    On 4ea3bed, each `#` import was an external import.

    The rule: Node.js "Subpath imports" (https://nodejs.org/api/packages.html#subpath-imports)
    and PACKAGE_IMPORTS_RESOLVE in https://nodejs.org/api/esm.html, with the conditions
    of TypeScript ("package.json "imports" and self-name imports" in
    https://www.typescriptlang.org/docs/handbook/modules/reference.html): `types`,
    `node`, `import` or `require`, and `default`. A `.cts` file is CommonJS, so it
    matches `require`. The first matched key in file order gives the target, and a null
    value stops the search. `#types/shapes` gives a declaration file, which has no
    module. Node.js cannot load that file, so the import is a type-only dependency and
    not an unresolved import (trial2-1: on 2c7b1f8, it was an unresolved import). `#fs`
    names a Node.js module, which `external` does not include.
    """
    components = _build(tmp_path, SUBPATH)["components"]
    record = components["web.main"]
    assert record["uses"] == {
        "web.esm": ["f"],
        "web.internal.deep": ["d"],
        "web.util": ["u"],
    }
    assert record["external"] == ["left-pad"]
    assert record["completeness"]["unresolved_imports"] == ["#blocked", "#missing"]
    assert components["web.legacy"]["uses"] == {"web.cjs": ["f"]}


# The syntax that tree-sitter-typescript 0.23.2 refuses (trial-16): a generic call with
# a `typeof import()` type argument and a trailing comma in its arguments. The same call
# without the trailing comma, or with `typeof x`, parses. 0.23.2 is the latest release
# on PyPI and npm, and the grammar has no later change (measured 2026-10-13).
GRAMMAR_LIMIT = (
    'test("cjs", async () => {\n'
    "  await expect(() =>\n"
    "    runnerImport<typeof import('./fixtures/basic')>(\n"
    "      fixture('cjs.js'),\n"
    "    ),\n"
    "  ).rejects.toThrow('module is not defined')\n"
    "})\n"
)


def test_a_parse_problem_gives_the_error_lines_and_the_parser_version(tmp_path: Path) -> None:
    """trial-16. Acceptance: the unknown record of the test file gives line 4, an excerpt
    that contains `runnerImport<typeof import('./fixtures/basic')>(` and
    `fixture('cjs.js'),`, and the parser version. On 4ea3bed, the excerpt was `','`
    and the line gave no parser version. From facts format 11, the reason is fixed, and
    the parser version is in the field `parser` (trial3-1).
    """
    facts = _build(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "tsconfig.json": "{}",
            "src/index.ts": "export const x = 1;\n",
            "src/__tests__/runner.spec.ts": GRAMMAR_LIMIT,
        },
    )
    [issue] = facts["test_file_issues"]
    problem = issue["problem"]
    assert problem["line"] == 4
    assert problem["source"] == (
        "runnerImport<typeof import('./fixtures/basic')>( fixture('cjs.js'),"
    )
    assert problem["reason"] == "The parser could not parse the source syntax."
    assert problem["parser"].startswith("tree-sitter ")
    assert "tree-sitter-typescript " in problem["parser"]


def test_an_answer_for_the_earlier_parse_line_applies_to_the_current_line(
    tmp_path: Path,
) -> None:
    """trial-16. Acceptance: an exact answer with the earlier line (excerpt `','` and no
    parser version) applies to the current line of the same file and line, with the
    same evidence digest. A finding line is an identifier (`AGENTS.md`), so the change
    of the line needs this migration."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "tsconfig.json": "{}",
            "src/runner.ts": GRAMMAR_LIMIT,
        },
    )
    lines = source_facts.unknown_fact_lines(extract.build(config.load(tmp_path)))
    [line] = [line for line in lines if "web.runner" in line]
    earlier = line.replace("(src/runner.ts)", "(src/runner.ts:4)") + " Source excerpt: ','"
    answer = Answer(items=(earlier,), reason="known", evidence="digest")
    # From facts format 11, `answer_migrations` gives the current line (trial3-1).
    assert answer_migrations.current_line(earlier) == line
    [moved] = answer_migrations.current_lines([answer], [line])
    result = judgement.apply_answers([line], [moved], {line: "digest"})
    assert result.open == [] and result.stale == [] and result.pending == []
