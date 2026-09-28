"""Focused contracts for source and workflow accuracy failures."""

from __future__ import annotations

import ast
import dataclasses
import json
import subprocess
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import change, check, config, extract, history, journeys, scaffold
from systemap.jev_cli import _atomic_model_write
from systemap.journeys import as_source
from systemap.model import Component, Flow, Journey, Model, Step
from systemap.typescript import TYPESCRIPT
from systemap.typescript_surface import parse_surface as typescript_surface
from systemap.typescript_surface import test_names as typescript_test_names


def test_parse_failure_remains_in_inventory(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/bad.py": "def broken(:\n"})
    facts = extract.build(config.load(tmp_path))
    assert "pkg.bad" in facts["components"]
    assert facts["components"]["pkg.bad"]["parse_error"]["line"] == 1


def test_syntax_digest_ignores_formatting_but_tracks_behavior(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text("def run():\n    return 1\n")
    before = extract.collect_module(path, tmp_path)
    path.write_text("# explanation\ndef run(): return 1\n")
    formatted = extract.collect_module(path, tmp_path)
    path.write_text("def run(): return 2\n")
    changed = extract.collect_module(path, tmp_path)
    assert before is not None and formatted is not None and changed is not None
    assert before["sha"] != formatted["sha"]
    assert before["syntax_sha"] == formatted["syntax_sha"]
    assert before["syntax_sha"] != changed["syntax_sha"]


def test_dotted_python_root_is_internal() -> None:
    source = "from ns.pkg.b import run\n"
    assert extract.internal_uses(source, {"ns.pkg"}, {"ns.pkg.a", "ns.pkg.b"}, "ns.pkg.a") == {
        "ns.pkg.b": {"run"}
    }
    assert extract.external_imports(source, {"ns.pkg"}) == []


def test_interface_member_belongs_to_named_class() -> None:
    surface = extract.parse_surface("class Item: pass\ndef run(): pass\n")
    assert surface is not None
    card = Component("A", "Reads.", implemented_by=("pkg.a",), interface="Item.run()")
    assert check.interface_problem(card, {"pkg.a": surface})


def test_interface_member_may_belong_to_reexported_module() -> None:
    root = extract.parse_surface(
        "from . import core", module="pkg", is_package=True, prefixes=frozenset({"pkg"})
    )
    core = extract.parse_surface("def run(): pass\n")
    assert root is not None and core is not None
    root["names"] = [{"name": "core", "kind": "module", "reexport_of": "pkg.core"}]
    card = Component("A", "Runs.", implemented_by=("pkg",), interface="core.run()")
    assert not check.interface_problem(card, {"pkg": root, "pkg.core": core})


def test_test_methods_have_distinct_identities(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/value.py": "def run(): return 1\n",
            "tests/test_value.py": (
                "from pkg.value import run\n"
                "class TestOne:\n def test_value(self): assert run() == 1\n"
                "class TestTwo:\n def test_value(self): assert run() == 1\n"
            ),
        },
    )
    record = extract.build(config.load(tmp_path))["components"]["pkg.value"]
    assert record["tests_total"] == 2
    assert len(set(record["tests"])) == 2


def test_generated_journey_strings_round_trip() -> None:
    sentence = 'A sends the "value" \\ path.\nNext line: café.'
    journey = Journey(
        id="quoted",
        label=sentence,
        starts="GET /read",
        steps=(Step(acts=("A",), measures=("B",), edge=("A", "B"), say=sentence),),
    )
    source = (
        "from systemap.model import Journey, Step\nJOURNEYS = (\n"
        + "\n".join(as_source(journey))
        + "\n)\n"
    )
    ast.parse(source)
    namespace: dict[str, object] = {}
    exec(source, namespace)
    assert namespace["JOURNEYS"][0].label == sentence  # type: ignore[index]
    assert namespace["JOURNEYS"][0].steps[0].say == sentence  # type: ignore[index]


def test_journey_insertion_uses_code_anchor() -> None:
    journey = Journey("walk", "Read", (), starts="GET /read")
    source = 'NOTE = "JOURNEYS = ("\nJOURNEYS = (\n)\n'
    grown = journeys.add_to_source(source, journey)
    assert grown is not None
    ast.parse(grown)
    assert grown.startswith('NOTE = "JOURNEYS = ("\nJOURNEYS = (')


def test_invalid_generated_source_preserves_model(tmp_path: Path) -> None:
    path = tmp_path / "model.py"
    original = b"JOURNEYS = ()\n"
    path.write_bytes(original)
    with pytest.raises(SyntaxError):
        _atomic_model_write(path, "JOURNEYS = (\n")
    assert path.read_bytes() == original


def test_invalid_journey_is_rejected_as_a_whole() -> None:
    point = {"kind": "route", "name": "GET /read", "module": "pkg.a", "target": "run"}
    group = journeys.Group((point,), "A")
    model = Model(
        (1000, 1000),
        (),
        (),
        (
            Component("A", "Reads.", implemented_by=("pkg.a",)),
            Component("B", "Writes.", implemented_by=("pkg.b",)),
        ),
        (Flow("A", "B", "value", "data"),),
        (),
    )
    valid = {"edge": ["A", "B"], "acts": ["A"], "measures": [], "say": "A sends a value."}
    answer = json.dumps(
        {"id": "walk", "label": "Read", "steps": [valid, {**valid, "edge": ["B", "A"]}]}
    )
    draft = journeys.read_answer(answer, model, group)
    assert draft.journey is None
    assert draft.problems
    assert draft.answer == answer


def test_typescript_ci_installs_parser_extra() -> None:
    workflow = scaffold.files("Web", "web", [("src", "web")], language="typescript")[
        ".github/workflows/systemap.yml"
    ]
    assert workflow.count("systemap[typescript]==") == workflow.count("uvx --from")


def test_javascript_private_method_is_not_public() -> None:
    surface = typescript_surface("export class Item { #hidden() {} public visible() {} }")
    assert surface is not None
    assert surface["classes"][0]["methods"] == ["public visible()"]


def test_typescript_test_modifiers_keep_literal_names() -> None:
    assert typescript_test_names(
        'test.only("one", () => {}); it.concurrent("two", () => {}); test("three", () => {});'
    ) == ["one", "two", "three"]


def test_typescript_test_total_precedes_display_cap(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\ntests_dir = "tests"\n'
            '[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/value.ts": "export const value = 1;\n",
            "tests/value.test.ts": 'import { value } from "../src/value";\n'
            + "\n".join(f'test("case {i}", () => value)' for i in range(30)),
        },
    )
    record = extract.build(config.load(tmp_path))["components"]["web.value"]
    assert record["tests_total"] == 30
    assert len(record["tests"]) <= 25


def test_reexport_chain_keeps_function_kind_and_entry(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/a.ts": 'export { run } from "./middle";',
            "src/middle.ts": 'export { run } from "./z";',
            "src/z.ts": "export function run(): void {}",
            "src/index.ts": 'export { run } from "./a";',
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert facts["components"]["web.index"]["names"] == [
        {"name": "run", "kind": "function", "reexport_of": "web.a"}
    ]
    assert any(
        point["module"] == "web.index" and point["name"] == "run" for point in facts["entry_points"]
    )


def test_conflicting_star_exports_are_uncertain(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/a.ts": "export function run(): void {}",
            "src/b.ts": "export function run(): void {}",
            "src/index.ts": 'export * from "./a"; export * from "./b";',
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert any("ambiguous" in line for line in extract.unknown_fact_lines(facts))


@pytest.mark.parametrize(
    ("specifier", "files", "options", "expected"),
    [
        (
            "./foo.bar.js",
            {"src/foo.bar.ts": "export const value = 1;", "src/foo.ts": "export const value = 2;"},
            {},
            "web.foo.bar",
        ),
        (
            "@/special/value",
            {
                "src/general/special/value.ts": "export const value = 1;",
                "src/specific/value.ts": "export const value = 2;",
            },
            {
                "baseUrl": ".",
                "paths": {"@/*": ["src/general/*"], "@/special/*": ["src/specific/*"]},
            },
            "web.specific.value",
        ),
        (
            "web/value",
            {"src/value.ts": "export const value = 1;", "src/actual.ts": "export const value = 2;"},
            {"baseUrl": ".", "paths": {"web/value": ["src/actual.ts"]}},
            "web.actual",
        ),
        (
            "./value",
            {"src/generated/value.ts": "export const value = 1;"},
            {"baseUrl": ".", "rootDirs": ["src", "src/generated"]},
            "web.generated.value",
        ),
    ],
)
def test_typescript_resolution_matches_supported_cases(
    tmp_path: Path,
    specifier: str,
    files: dict[str, str],
    options: dict[str, object],
    expected: str,
) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": json.dumps({"compilerOptions": options}),
            "src/entry.ts": f'import {{ value }} from "{specifier}"; export const result = value;',
            **files,
        },
    )
    uses = extract.build(config.load(tmp_path))["components"]["web.entry"]["uses"]
    assert list(uses) == [expected]


@pytest.mark.parametrize(
    "source",
    [
        'export async function load() { return import("./value"); }',
        'import value = require("./value"); export const result = value;',
    ],
)
def test_typescript_literal_import_forms_are_dependencies(tmp_path: Path, source: str) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/entry.ts": source,
            "src/value.ts": "export const value = 1;",
        },
    )
    uses = extract.build(config.load(tmp_path))["components"]["web.entry"]["uses"]
    assert "web.value" in uses


def test_typescript_emit_root_includes_imported_inputs(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": json.dumps(
                {
                    "name": "web",
                    "devDependencies": {"typescript": "5.9.3"},
                    "bin": {"correct": "out/src/cli.js", "wrong": "out/cli.js"},
                }
            ),
            "tsconfig.json": json.dumps(
                {"include": ["src"], "compilerOptions": {"outDir": "out", "module": "commonjs"}}
            ),
            "src/cli.ts": 'import { value } from "../shared/value"; console.log(value);',
            "shared/value.ts": "export const value = 1;",
        },
    )
    facts = extract.build(config.load(tmp_path))
    bins = {
        point["name"]: point["module"]
        for point in facts["entry_points"]
        if point["kind"] == "console_script"
    }
    assert bins == {"correct": "web.cli"}


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("export interface Item { id: string }", "export interface Item { id: number }"),
        ("export type Item = string;", "export type Item = number;"),
        ("export enum Item { One = 1 }", "export enum Item { One = 2 }"),
        ("export class Item { id: string = ''; }", "export class Item { id: number = 0; }"),
        (
            "export const run = <T extends string>(x: T): T => x;",
            "export const run = <T extends number>(x: T): T => x;",
        ),
        (
            "function run(x: string) {} export { run };",
            "function run(x: number) {} export { run };",
        ),
        ("function run(x: string) {} export { run };", "function run(x: string) {}"),
        ('export { run } from "./impl";', ""),
        (
            "export function run(x: string): string; export function run(x: any): any { return x; }",
            "export function run(x: number): number; export function run(x: any): any { return x; }",
        ),
        ("export const settings = { retries: 2 };", ""),
    ],
)
def test_typescript_exported_contract_changes_are_visible(before: str, after: str) -> None:
    delta = change.surface_delta(before, after, TYPESCRIPT, "src/api.ts")
    assert (
        delta is None
        or delta.get("unknown")
        or any(
            delta[part][bucket]
            for part in ("added", "removed", "changed")
            for bucket in change.BUCKETS
        )
    )


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            "class Item:\n def __init__(self, x): pass",
            "class Item:\n def __init__(self, x, y): pass",
        ),
        (
            "from dataclasses import dataclass\n@dataclass\nclass Item:\n value: int",
            "from dataclasses import dataclass\n@dataclass\nclass Item:\n value: str",
        ),
        ("app = object()", ""),
        ("from .core import run", ""),
    ],
)
def test_python_exported_contract_changes_are_visible(before: str, after: str) -> None:
    delta = change.surface_delta(before, after)
    assert (
        delta is None
        or delta.get("unknown")
        or any(
            delta[part][bucket]
            for part in ("added", "removed", "changed")
            for bucket in change.BUCKETS
        )
    )


def test_alias_change_invalidates_stored_facts(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/one/*"]}}}',
            "src/entry.ts": 'import { value } from "@/value"; export const result = value;',
            "src/one/value.ts": "export const value = 1;",
            "src/two/value.ts": "export const value = 2;",
        },
    )
    cfg = config.load(tmp_path)
    before = extract.build(cfg)
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/two/*"]}}}'
    )
    after = extract.build(cfg)
    assert before["components"]["web.entry"]["uses"] != after["components"]["web.entry"]["uses"]
    assert extract.drift(after, before)
    assert extract.drift(after, after) == []


def test_invalid_change_ref_is_an_error(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/value.py": "def run(): pass\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    cfg = config.load(tmp_path)
    model = Model((1000, 1000), (), (), (), (), ())
    with pytest.raises(change.ChangeError, match="missing"):
        change.compute(cfg, model, "missing", extract.build(cfg))


def test_historical_change_uses_head_graph_and_symbol_claims(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/a.py": "def run(): return 1\n",
            "pkg/b.py": "from pkg.a import run\n",
        },
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "pkg/a.py").write_text("def run(): return 2\n")
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "head",
    )
    head = git(tmp_path, "rev-parse", "HEAD")
    cfg = config.load(tmp_path)
    target_facts = extract.build(cfg)
    (tmp_path / "pkg/b.py").write_text("def independent(): return 3\n")
    working_facts = extract.build(cfg)
    model = Model(
        (1000, 1000),
        (),
        (),
        (
            Component("A", "Reads.", implemented_by=("pkg.a",)),
            Component("B", "Uses.", implemented_by=("pkg.b",)),
            Component("Symbol", "Runs.", implemented_by=("pkg.a:run",)),
        ),
        (),
        (),
    )
    got = change.compute(cfg, model, base, working_facts, head)
    assert got["adjacent"] == change.compute(cfg, model, base, target_facts, head)["adjacent"]
    assert "B" in got["adjacent"]
    assert "Symbol" in got["direct"]


def test_historical_facts_cache_uses_extraction_configuration(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/value.py": "def run(): pass\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    sha = git(tmp_path, "rev-parse", "HEAD")
    cfg = config.load(tmp_path)
    first = history.facts_at(cfg, sha)
    renamed = dataclasses.replace(cfg, package_roots=(("pkg", "other"),))
    second = history.facts_at(renamed, sha)
    assert "pkg.value" in first["components"]
    assert "other.value" in second["components"]


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
