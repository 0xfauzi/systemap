"""Trial results for `init`, the test files, the module description, and the facts views
(trial-5, trial-7, trial-8, trial-9, trial-10).

A trial operated systemap 4ea3bed on the ky and vite repositories. These fixtures copy
the layouts of those repositories in a few files.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, extract
from systemap import facts as facts_view
from systemap.cli import main

# The ky layout: tsconfig.json includes only `source`, and tsd type tests are in test-d.
KY = {
    "package.json": '{"name": "web", "type": "module"}',
    "tsconfig.json": '{"compilerOptions": {"strict": true}, "include": ["source"]}',
    "source/index.ts": "/*! MIT License © Web Authors */\n\nexport function start(): void {}\n",
    "test-d/start.ts": 'import { start } from "../source/index";\nstart();\n',
    "test/start.ts": 'import { start } from "../source/index";\ntest("start", start);\n',
}
# The vite layout: no tsconfig.json at the root, and type tests in __tests_dts__.
VITE = {
    "package.json": '{"name": "mono", "private": true}',
    "vitest.config.ts": "export default {};\n",
    "packages/core/package.json": '{"name": "@acme/core"}',
    "packages/core/tsconfig.json": "{}",
    "packages/core/src/index.ts": "export const core = 1;\n",
    "packages/core/src/node/__tests_dts__/config.ts": 'import { core } from "../../index";\n',
    "packages/core/src/node/plugin.spec-d.ts": 'import { core } from "../index";\n',
    "packages/cli/tsconfig.json": "{}",
    "packages/cli/src/main.ts": "export const main = 1;\n",
}


def _init(root: Path, tree: dict[str, str], capsys: pytest.CaptureFixture[str]) -> str:
    write_tree(root, tree)
    assert main(["--root", str(root), "init", "--no-ci"]) == 0
    return capsys.readouterr().out


def _toml(root: Path) -> dict[str, Any]:
    with (root / "systemap.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_init_selects_the_one_include_folder_of_tsconfig(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial-5 and trial-7. Acceptance: init writes `"source" = "web"` and
    `test_patterns = ["**/test-d/**"]`. The facts then hold only `web.index`. On 4ea3bed,
    init wrote `"." = "web"`, and the test-d file was the module `web.test_d.start`.

    The rule is in the configuration: the `include` entries of tsconfig.json name one
    source folder, and init writes the type-test folder in `test_patterns`.
    """
    _init(tmp_path, KY, capsys)
    settings = _toml(tmp_path)
    assert settings["package_roots"] == {"source": "web"}
    assert settings["test_patterns"] == ["**/test-d/**"]
    facts = extract.build(config.load(tmp_path))
    assert sorted(facts["components"]) == ["web.index"]


@pytest.mark.parametrize(
    ("include", "root"),
    [
        (["source", "test-d"], "source"),
        (["source/**/*.ts"], "source"),
        (["source", "vite.config.ts"], "."),
        (["source", "scripts"], "."),
    ],
)
def test_the_include_rule_needs_folder_entries_and_one_source_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], include: list[str], root: str
) -> None:
    """trial-5. Acceptance: a test folder in `include` does not count, and a pattern
    names the folder before its first wildcard. An entry that names a file, or two
    source folders, give the earlier rule: src, then the repository root."""
    tree = dict(KY, **{"vite.config.ts": "export default {};\n", "scripts/x.ts": "1;\n"})
    tree["tsconfig.json"] = '{"include": ' + str(include).replace("'", '"') + "}"
    _init(tmp_path, tree, capsys)
    assert _toml(tmp_path)["package_roots"] == {root: "web"}


def test_init_without_roots_gives_the_table_to_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial-8 and trial-7. Acceptance: init prints the cause and the exact table, with
    one line for each package folder that has a tsconfig.json file. extract gives the
    same text, and not the incorrect "No .ts or .tsx source is available in src or the
    repository root" (the root has vitest.config.ts). After the table goes into
    systemap.toml, extract operates, and the type tests are not modules.
    """
    out = _init(tmp_path, VITE, capsys)
    table = '[package_roots]\n"packages/cli/src" = "cli"\n"packages/core/src" = "acme.core"'
    assert "The repository root has no tsconfig.json file." in out
    assert table in out
    assert _toml(tmp_path)["test_patterns"] == ["**/*.spec-d.*", "**/__tests_dts__/**"]
    assert main(["--root", str(tmp_path), "extract"]) == 2
    err = capsys.readouterr().err
    assert table in err and "No .ts or .tsx source is available" not in err
    path = tmp_path / "systemap.toml"
    path.write_text(path.read_text(encoding="utf-8") + "\n" + table + "\n", encoding="utf-8")
    facts = extract.build(config.load(tmp_path))
    assert sorted(facts["components"]) == ["acme.core.index", "cli.main"]


def test_python_init_without_roots_also_gives_the_instruction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial-8, the same behavior for Python. Acceptance: init in a Python repository
    without a package prints the text that extract gives later."""
    out = _init(tmp_path, {"script.py": "print(1)\n"}, capsys)
    assert "No package roots are available." in out
    assert '("path" = "import name")' in out


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("/*! MIT License © Web */\n\nexport const x = 1;\n", ""),
        ("/*! MIT */\n/** Reads files. */\n\nexport const x = 1;\n", "Reads files."),
        (
            "// Copyright 2020 Web LLC\n//\n// Licensed under the Apache License.\n\n"
            "// Reads files.\n\nexport const x = 1;\n",
            "Reads files.",
        ),
        ("/**\n * @license\n * Copyright Web\n */\nexport const x = 1;\n", ""),
        ("/** Reads files. */\n\nexport const x = 1;\n", "Reads files."),
    ],
)
def test_a_typescript_license_notice_is_not_a_description(
    tmp_path: Path, source: str, expected: str
) -> None:
    """trial-9. Acceptance: each notice gives an empty description, and the next comment
    can give the description. On 4ea3bed, `/*! MIT License © Web */` gave the
    description "! MIT License © Web", and `facts --modules` showed "!".

    The rule (`notice_text`): a legal comment of esbuild starts with `/*!` or `//!`
    (https://esbuild.github.io/api/#legal-comments). A text that starts with
    `Copyright`, `©`, `(c)`, `SPDX-`, `Licensed under`, `@license`, or `@preserve` is a
    notice. The `//` comments on the lines directly below a notice are part of it.
    """
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "tsconfig.json": "{}",
            "src/reader.ts": source,
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert facts["components"]["web.reader"]["docstring"] == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('"""Copyright 2024 Tool Authors.\n\nLicensed under MIT."""\n', ""),
        ('"""SPDX-License-Identifier: MIT"""\n', ""),
        ('# Copyright 2024 Tool Authors.\n"""Reads files."""\n', "Reads files."),
        ('"""Reads files.\n\n:copyright: 2024 Tool Authors."""\n', "Reads files."),
    ],
)
def test_a_python_license_notice_is_not_a_description(
    tmp_path: Path, source: str, expected: str
) -> None:
    """trial-9, the same rule for Python. Acceptance: a docstring that starts with a
    notice mark gives an empty description. A `#` comment is not a docstring, and a
    notice after the first paragraph does not change the description. On 4ea3bed, the
    first docstring gave "Copyright 2024 Tool Authors."
    """
    write_tree(tmp_path, {"tool/__init__.py": "", "tool/reader.py": source})
    facts = extract.build(config.load(tmp_path))
    assert facts["components"]["tool.reader"]["docstring"] == expected


def test_the_entry_point_heading_names_no_python_term(tmp_path: Path) -> None:
    """trial-10. Acceptance: the `facts --entry-points` heading does not contain
    "console-script" or "subcommand". The `target` field has the same meaning for each
    language, so the heading names no language."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "tsconfig.json": "{}",
            "src/index.ts": "export function start(): void {}\n",
        },
    )
    heading = facts_view.entry_points(extract.build(config.load(tmp_path)))[0]
    assert heading.startswith("entry points: 1.")
    assert "console-script" not in heading and "subcommand" not in heading
