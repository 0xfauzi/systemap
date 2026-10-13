"""A TypeScript source file that is a link loop, at each place that resolves a source path.

`test_review2_python.py` has the plain case for Python and for TypeScript. These cases
put the loop in an import, an outDir, a package entry, and a workspace package. On the
base, each case stopped extraction with RuntimeError before the shared read.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, extract, unknown_causes

TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/tools.ts": "export function run(): void {}\n",
}


def _importer(specifier: str) -> str:
    return f'import {{ x }} from "{specifier}";\nexport function run(): void {{}}\n'


CASES = {
    # typescript_resolve.relative_targets
    "import": ({"src/tools.ts": _importer("./loop.ts")}, "src/loop.ts", "web.loop"),
    # typescript_repo.ts_skipped
    "outdir": (
        {"tsconfig.json": '{"compilerOptions":{"outDir":"src/out"}}'},
        "src/loop.ts",
        "web.loop",
    ),
    # typescript_entry._matching_entry_modules
    "bin": (
        {"package.json": '{"name":"web","bin":{"web":"./src/loop.ts"}}'},
        "src/loop.ts",
        "web.loop",
    ),
    # typescript_config.source_targets
    "subpath": (
        {
            "package.json": '{"name":"web","imports":{"#loop":"./src/loop.ts"}}',
            "src/tools.ts": _importer("#loop"),
        },
        "src/loop.ts",
        "web.loop",
    ),
    # typescript_projects.package_directory
    "workspace": (
        {
            "package.json": '{"name":"root","workspaces":["src/pkg"]}',
            "src/pkg/package.json": '{"name":"pkg"}',
            "src/pkg/tools.ts": "export const y = 1;\n",
            "src/tools.ts": _importer("pkg/loop"),
        },
        "src/pkg/loop.ts",
        "web.pkg.loop",
    ),
}


@pytest.mark.skipif(sys.platform == "win32", reason="the test makes symbolic links")
@pytest.mark.parametrize("case", sorted(CASES))
def test_a_typescript_link_loop_at_each_resolve_is_a_module_that_could_not_be_read(
    tmp_path: Path, case: str
) -> None:
    """Acceptance: for each case, extraction gives no traceback. The loop module has
    `parsed` false and the cause `read`, as the plain case in `test_review2_python.py`."""
    files, loop, module = CASES[case]
    write_tree(tmp_path, {**TREE, **files})
    (tmp_path / loop).symlink_to(Path(loop).name)
    state = extract.build(config.load(tmp_path))["components"][module]["completeness"]
    assert state["parsed"] is False
    assert state["cause"] == unknown_causes.READ


@pytest.mark.skipif(sys.platform == "win32", reason="the test makes symbolic links")
def test_a_typescript_declaration_target_that_is_a_link_loop_is_not_a_dependency(
    tmp_path: Path,
) -> None:
    """Acceptance: a package `types` target that is a link loop gives no traceback and no
    declaration dependency (`typescript_package_imports._file_import`)."""
    write_tree(
        tmp_path,
        {
            **TREE,
            "package.json": '{"name":"web","exports":{"./loop":{"types":"./src/loop.d.ts"}}}',
            "src/tools.ts": _importer("web/loop"),
        },
    )
    (tmp_path / "src" / "loop.d.ts").symlink_to("loop.d.ts")
    facts = extract.build(config.load(tmp_path))
    assert "src/loop.d.ts" not in str(facts["components"]["web.tools"])
