"""Repairs of the second trial results (trial2-1 to trial2-6).

A second trial operated systemap 2c7b1f8 on click, httpx, ky, and vite. Each test gives a
small fixture that copies the layout of one result. No test clones a repository. Each
acceptance value is in the docstring of its test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_trial_check import SOURCES, UNREAD, mapped_project

from systemap import (
    answer_migrations,
    config,
    explain,
    extract,
    import_rules,
    journey_coverage,
    judgement_json,
    source_facts,
    trend,
    unknown_causes,
)
from systemap.cli import main
from systemap.config import Answer
from systemap.model import Component, ImportRule, Model

# ---- trial2-1: a target that is a declaration file -----------------------------------

# The vite layout: package.json maps `#types/*` and `#dep-types/*` to declaration files.
DECLARATIONS = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": json.dumps(
        {
            "name": "web",
            "imports": {
                "#types/*": "./types/*.d.ts",
                "#dep-types/*": "./src/types/*.d.ts",
                "#typed": {"types": "./types/typed.d.ts", "default": "./dist/typed.js"},
            },
        }
    ),
    "tsconfig.json": "{}",
    "types/shapes.d.ts": "export type Shape = string;\nexport type Size = number;\n",
    "types/typed.d.ts": "export type Typed = string;\n",
    "src/types/deps.d.ts": "export type Dep = string;\n",
    "src/index.ts": (
        "export const x = 1\n"
        "\n"
        "export type {\n"
        "  Shape,\n"
        "  Size,\n"
        "} from '#types/shapes'\n"
        "export type { Dep } from '#dep-types/deps'\n"
        "export type { Missing } from '#types/missing'\n"
        "export * from '#types/shapes'\n"
    ),
    "src/user.ts": (
        "import type { Shape } from '#types/shapes'\n"
        "import type { Dep } from '#dep-types/deps'\n"
        "export const s: Shape | Dep = 'a'\n"
    ),
    "src/typed.ts": "import type { Typed } from '#typed'\nexport const t: Typed = 'a'\n",
}
DECLARED = (
    "the re-export target '{target}' is the declaration file {file}. A declaration file "
    "gives only types and has no module record. Names: {names}."
)
OUTSIDE = "the re-export target '{target}' is outside the extracted module set."


def _build(root: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(root, tree)
    return extract.build(config.load(root))


def test_a_reexport_of_a_declaration_file_gives_one_line_for_each_statement(
    tmp_path: Path,
) -> None:
    """trial2-1. Acceptance: `src/index.ts` gives 4 unknown lines, one for each re-export
    statement. The sources of the lines give the line of each statement (3, 7, 8, 9).
    From facts format 11, a line has no line number (trial3-1).
    The three statements that name an existing declaration file have the cause
    `declaration file`, the file, and the names of the statement. The statement with a
    missing file keeps the cause `target` and gives its name. No two lines are equal.

    On 2c7b1f8, the module gave 4 lines at `src/index.ts:1`, each with the cause
    `target`: the statement with two names gave 2 equal lines, and no line gave a name.
    """
    facts = _build(tmp_path, DECLARATIONS)
    causes = source_facts.unknown_fact_causes(facts)
    lines = [(line, cause) for line, cause in causes if "module web.index " in line]
    head = "unknown surface: module web.index (src/index.ts): "
    shapes = {"target": "#types/shapes", "file": "types/shapes.d.ts"}
    assert lines == [
        (
            head + DECLARED.format(**shapes, names="Shape, Size"),
            unknown_causes.DECLARATION_FILE,
        ),
        (
            head
            + DECLARED.format(target="#dep-types/deps", file="src/types/deps.d.ts", names="Dep"),
            unknown_causes.DECLARATION_FILE,
        ),
        (
            head + OUTSIDE.format(target="#types/missing") + " Names: Missing.",
            unknown_causes.TARGET,
        ),
        (
            head + DECLARED.format(**shapes, names="*"),
            unknown_causes.DECLARATION_FILE,
        ),
    ]
    assert len({line for line, _cause in causes}) == len(causes)
    located = source_facts.located_records(facts)
    assert [[found.line for found in located[line]] for line, _cause in lines] == [
        [3],
        [7],
        [8],
        [9],
    ]


def test_an_import_of_a_declaration_file_is_not_an_unresolved_import(tmp_path: Path) -> None:
    """trial2-1. Acceptance: in `src/user.ts`, `#types/shapes` and `#dep-types/deps` are
    not unresolved imports, and not external imports. An import rule that reads the
    module gives `pass`. On 2c7b1f8, both were unresolved local imports, and the rule
    gave `unknown`.

    `#typed` gives a declaration file under the condition `types`, but `default` gives a
    script file with no source module. Node.js loads that script file, so the import is
    not type-only: it stays an unresolved local import, and a rule that reads the
    module gives `unknown`.
    """
    facts = _build(tmp_path, DECLARATIONS)
    user = facts["components"]["web.user"]
    assert user["completeness"]["unresolved_imports"] == []
    assert user["external"] == [] and user["uses"] == {}
    typed = facts["components"]["web.typed"]
    assert typed["completeness"]["unresolved_imports"] == ["#typed"]
    cards = (
        Component("User", "Uses types.", implemented_by=("web.user",)),
        Component("Typed", "Uses a typed file.", implemented_by=("web.typed",)),
    )
    rules = (
        ImportRule("user", "forbid_cycle", ("User",)),
        ImportRule("typed", "forbid_cycle", ("Typed",)),
    )
    model = Model((900, 400), (), (), cards, (), (), import_rules=rules)
    ruled = import_rules.evaluate(model, facts)
    assert [outcome.result for outcome in ruled] == [import_rules.PASS, import_rules.UNKNOWN]


def test_the_declaration_file_cause_has_a_fix_that_the_user_can_do() -> None:
    """trial2-1. Acceptance: the cause `declaration file` has its own fix text. The text
    tells the user to examine the declaration file and to record an answer. It does not
    tell the user to add a directory to [package_roots], because a declaration file is
    never a module."""
    text = unknown_causes.FIX[unknown_causes.DECLARATION_FILE]
    assert unknown_causes.DECLARATION_FILE in unknown_causes.CAUSES
    assert "[judgement] answered" in text and "Examine the declaration file" in text
    assert "package_roots" not in text
    assert unknown_causes.fix_lines([unknown_causes.DECLARATION_FILE]) == [f"  fix: {text}"]


def test_an_answer_for_the_earlier_reexport_target_line_selects_the_new_line() -> None:
    """trial2-1. Acceptance: an answer item in the earlier form (location `:1`, no
    names) selects the current line of the same module and target, with and without a
    map prefix, if one current line agrees. If two current lines agree, the item stays
    as it is (the answer is stale). The earlier form of a declaration file line does not
    select the new declaration file line, because the meaning changed."""
    earlier = (
        "unknown surface: module web.index (src/index.ts:1): the re-export target "
        "'#types/missing' is outside the extracted module set."
    )
    current = (
        "unknown surface: module web.index (src/index.ts): the re-export target "
        "'#types/missing' is outside the extracted module set. Names: Missing."
    )
    declared = (
        "unknown surface: module web.index (src/index.ts): the re-export target "
        "'#types/shapes' is the declaration file types/shapes.d.ts. A declaration file "
        "gives only types and has no module record. Names: Shape, Size."
    )
    old_shapes = earlier.replace("#types/missing", "#types/shapes")
    for prefix in ("", "Web: "):
        given = [Answer(items=(prefix + earlier, prefix + old_shapes), reason="known")]
        [moved] = answer_migrations.current_lines(given, [prefix + current, prefix + declared])
        assert moved.items == (prefix + current, prefix + old_shapes)
    second = current.replace("Missing.", "Other.")
    [kept] = answer_migrations.current_lines(
        [Answer(items=(earlier,), reason="known")], [current, second]
    )
    assert kept.items == (earlier,)


# ---- trial2-2: judgement gives the cause and the fix line ----------------------------


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_judgement_gives_the_cause_and_the_fix_line_of_an_unknown_surface_line(
    tmp_path: Path, language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """trial2-2. Acceptance: in 2 of 2 languages, with a module that does not parse,
    `judgement` prints the row `cause: syntax` below the `unknown surface` line and the
    fix line of the cause `syntax`. `--brief` keeps the two rows. `judgement --json`
    gives `"cause": "syntax"` in the row of that line, null in each other row, and
    `schema_version` 3. The explanation does not say "Read the source excerpt", because
    a line can have no excerpt. On 2c7b1f8, the text and the JSON object had no cause
    and no fix line, but the explanation told the reader to do the step in the fix line.
    """
    file, _module, _card = UNREAD[language]
    root = mapped_project(tmp_path, language)
    write_tree(root, {file: SOURCES[(language, "syntax error")]})
    assert main(["--root", str(root), "refresh"]) == 0
    fix = f"  fix: {unknown_causes.FIX[unknown_causes.SYNTAX]}"
    for brief in ((), ("--brief",)):
        capsys.readouterr()
        main(["--root", str(root), "judgement", *brief])
        rows = capsys.readouterr().out.splitlines()
        surface = [k for k, row in enumerate(rows) if row.startswith("  unknown surface: ")]
        assert surface, rows
        assert all(rows[k + 1] == "    cause: syntax" for k in surface)
        assert fix in rows
    capsys.readouterr()
    main(["--root", str(root), "judgement", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["schema_version"] == 6
    causes = {row["line"]: row["cause"] for row in out["open"]}
    assert {c for line, c in causes.items() if "unknown surface: " in line} == {"syntax"}
    assert {c for line, c in causes.items() if "unknown surface: " not in line} == {None}
    assert "source excerpt" not in explain.JUDGEMENT["unknown surface"].do


def test_the_cause_row_uses_the_line_of_a_nested_map() -> None:
    """trial2-2. Acceptance: a line with a nested-map prefix gets the cause of the same
    line without the prefix."""
    facts = {"config_issues": [{"file": "a.json", "reference": "@x/y", "cause": "package"}]}
    [(line, _cause)] = source_facts.unknown_fact_causes(facts)
    thin = "thin layer: a shows 0 components"
    found = judgement_json.line_causes([f"Web: {line}", thin], facts)
    assert found == {f"Web: {line}": unknown_causes.PACKAGE}


# ---- trial2-3: a string export name ------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "export { viteLegacyPluginCjs as 'module.exports' }",
        'export { viteLegacyPluginCjs as "module.exports" }',
    ],
)
def test_a_string_export_name_is_the_public_name(tmp_path: Path, statement: str) -> None:
    """trial2-3. Acceptance: `export { viteLegacyPluginCjs as 'module.exports' }` gives the
    public name `module.exports` in `names`, `functions`, and `api`, and the entry point
    `module.exports` of kind `public_function`. No record has the public name
    `viteLegacyPluginCjs`. On 2c7b1f8, each record gave `viteLegacyPluginCjs`.

    A re-export `export { 'a-b' as c } from './m'` gives the public name `c` and reads
    the name `a-b` of `./m`."""
    facts = _build(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name": "web", "exports": "./src/index.ts"}',
            "tsconfig.json": "{}",
            "src/index.ts": (
                "function viteLegacyPluginCjs(): void {}\n"
                f"{statement}\n"
                "export { 'a-b' as c } from './m'\n"
            ),
            "src/m.ts": "const value = 1\nexport { value as 'a-b' }\n",
        },
    )
    record = facts["components"]["web.index"]
    public = "module.exports"
    assert [entry["name"] for entry in record["names"]] == [public, "c"]
    assert [entry["name"] for entry in record["functions"]] == [public]
    assert [entry["name"] for entry in record["api"]] == [public, "c"]
    points = [p for p in facts["entry_points"] if p["module"] == "web.index"]
    assert [(p["kind"], p["name"]) for p in points] == [("public_function", public)]
    assert record["uses"] == {"web.m": ["a-b"]}
    assert [entry["name"] for entry in facts["components"]["web.m"]["names"]] == ["a-b"]


# ---- trial2-4: the component of a joined console script --------------------------------


def test_a_joined_console_script_names_the_component_of_its_module(tmp_path: Path) -> None:
    """trial2-4. Acceptance: the httpx layout gives one `entry point` line for the console
    script and the `main` function that it starts. The line names the component of the
    module that the console script names (`Client`), not the component of the module
    that defines the function (`Cli`). The line does not change, so no migration is
    necessary. The `entry point` explanation tells the reader that the function can be
    in a different component."""
    facts = _build(
        tmp_path,
        {
            "pyproject.toml": (
                '[project]\nname = "httpx"\nversion = "1"\n'
                '[project.scripts]\nhttpx = "httpx:main"\n'
            ),
            "systemap.toml": '[package_roots]\n"httpx" = "httpx"\n',
            "httpx/__init__.py": (
                "try:\n    from ._main import main\nexcept ImportError:\n"
                "    def main() -> None:\n        pass\n"
            ),
            "httpx/_main.py": "def main() -> None:\n    pass\n",
        },
    )
    starts = [p for p in facts["entry_points"] if p["kind"] in ("console_script", "main_function")]
    owner = {"httpx": "Client", "httpx._main": "Cli"}
    open_points = [p for p in starts if not journey_coverage._same_code(p, {*map(_id, starts)})]
    assert journey_coverage._entry_lines(open_points, owner) == [
        "entry point httpx (console script) has no sequence (component Client)"
    ]
    means = explain.JUDGEMENT["entry point"].means
    assert "module that the entry point names" in means


def _id(point: dict[str, str]) -> str:
    return source_facts.entry_identity(point)


# ---- trial2-5 and trial2-6: text that agrees with the data -----------------------------


def test_the_history_head_gives_the_minimum_interval() -> None:
    """trial2-5. Acceptance: the head line gives N days as the minimum interval between
    two adjacent samples, and says that the interval before the ref can be smaller. It
    does not say "one every N days", because a repository with a small number of commits
    gives samples that are more than N days apart. On 2c7b1f8, the line said "one every
    14 days"."""
    window = trend.Window(base="a" * 40, head="b" * 40)
    [head, _rest] = trend.report([window, window], Path("."), "1 year ago", 14, 3)
    assert head == (
        "history: 3 samples since 1 year ago. The minimum interval between two adjacent "
        "samples is 14 days, but the interval before the ref can be smaller. 0 of 2 "
        "windows changed the map."
    )


def test_the_thin_layer_explanation_agrees_with_a_layer_without_components() -> None:
    """trial2-6. Acceptance: for the line "thin layer: control shows 0 components", the
    meaning and the `why` row apply to a layer with 0 components. On 2c7b1f8, the `why`
    row told only about "A layer with one component"."""
    lesson = explain.JUDGEMENT["thin layer"]
    assert "A layer with no components has no flows." in lesson.means
    assert lesson.why.startswith("A layer with less than two components gives no information")
