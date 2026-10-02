"""Probe TypeScript accuracy without Jev or a coding agent.

Acceptance stated before execution: 100% of the explicit contracts below
must hold. A positive control must work; a challenge must preserve the fact
or explicitly report that it cannot. These selected counterexamples do not
estimate accuracy on a population of repositories. No production code changes.

Run with an installed compiler as the independent resolution reference:
uv run python bench/jev/typescript_accuracy_review.py /path/to/typescript.js
The companion Node script reads projects but never executes their source.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from accuracy_review import card, commit, git, model_of

from systemap import change, config, evidence, extract, scaffold
from systemap.cli import main as cli_main
from systemap.model import Flow, Meaning
from systemap.typescript import TYPESCRIPT
from systemap.typescript_surface import parse_surface, test_names

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
ROWS: list[dict[str, Any]] = []


def record(case: str, expected: str, met: bool, actual: Any, control: bool = False) -> None:
    ROWS.append(dict(case=case, expected=expected, met=met, actual=actual, control=control))


def write(root: Path, files: dict[str, str]) -> None:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


def project(root: Path, files: dict[str, str], settings: dict[str, Any] | None = None) -> None:
    write(
        root,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "package.json": '{"name":"web","devDependencies":{"typescript":"5.9.3"}}',
            "tsconfig.json": json.dumps(
                settings
                or {
                    "compilerOptions": {
                        "module": "esnext",
                        "moduleResolution": "bundler",
                        "target": "es2022",
                    },
                }
            ),
            **files,
        },
    )


def oracle(root: Path, compiler: str, **requests: Any) -> dict[str, Any]:
    result = subprocess.run(
        ["node", str(HERE / "typescript_oracle.cjs"), compiler],
        input=json.dumps({"root": str(root), **requests}),
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(json.loads(result.stdout))


def resolution_case(
    root: Path,
    compiler: str,
    name: str,
    specifier: str,
    files: dict[str, str],
    settings: dict[str, Any] | None = None,
    control: bool = False,
) -> None:
    project(
        root,
        {
            "src/entry.ts": f'import {{ value }} from "{specifier}"; export const result = value;',
            **files,
        },
        settings,
    )
    truth = oracle(root, compiler, imports=[{"specifier": specifier, "importer": "src/entry.ts"}])
    facts = extract.build(config.load(root))
    found = facts["components"]["web.entry"]
    targets = [facts["components"][key]["file"] for key in found["uses"]]
    expected = truth["imports"][0]["resolved"]
    record(
        name,
        "Resolve to the same source file as the compiler.",
        targets == [expected],
        {
            "compiler": truth,
            "systemap_targets": targets,
            "unknown": extract.unknown_fact_lines(facts),
        },
        control,
    )


def resolution_cases(root: Path, compiler: str) -> None:
    value = "export const value = 1;"
    resolution_case(
        root / "relative",
        compiler,
        "relative_js_control",
        "./value.js",
        {"src/value.ts": value},
        control=True,
    )
    resolution_case(
        root / "dotted",
        compiler,
        "dotted_filename",
        "./foo.bar.js",
        {"src/foo.bar.ts": value, "src/foo.ts": value},
    )
    options = {"module": "esnext", "moduleResolution": "bundler", "baseUrl": "."}
    resolution_case(
        root / "alias",
        compiler,
        "alias_specificity",
        "@/special/value",
        {
            "src/general/special/value.ts": value,
            "src/specific/value.ts": value,
        },
        {
            "compilerOptions": {
                **options,
                "paths": {"@/*": ["src/general/*"], "@/special/*": ["src/specific/*"]},
            }
        },
    )
    resolution_case(
        root / "shadow",
        compiler,
        "module_name_before_alias",
        "web/value",
        {
            "src/value.ts": value,
            "src/actual.ts": value,
        },
        {"compilerOptions": {**options, "paths": {"web/value": ["src/actual.ts"]}}},
    )
    resolution_case(
        root / "rootdirs",
        compiler,
        "rootdirs_resolution",
        "./value",
        {
            "src/generated/value.ts": value,
        },
        {"compilerOptions": {**options, "rootDirs": ["src", "src/generated"]}},
    )
    resolution_case(
        root / "alias_control",
        compiler,
        "alias_control",
        "@/value",
        {
            "src/value.ts": value,
        },
        {"compilerOptions": {**options, "paths": {"@/*": ["src/*"]}}},
        control=True,
    )


def surface_cases() -> None:
    pairs = [
        (
            "function_signature_control",
            "export function run(x: string): void {}",
            "export function run(x: number): void {}",
            True,
        ),
        (
            "constructor_control",
            "export class Item { constructor(x: string) {} }",
            "export class Item { constructor(x: number) {} }",
            True,
        ),
        (
            "interface_property",
            "export interface Item { id: string }",
            "export interface Item { id: number }",
            False,
        ),
        ("type_alias", "export type Item = string;", "export type Item = number;", False),
        ("enum_value", "export enum Item { One = 1 }", "export enum Item { One = 2 }", False),
        (
            "public_class_field",
            "export class Item { id: string = ''; }",
            "export class Item { id: number = 0; }",
            False,
        ),
        (
            "generic_constraint",
            "export const run = <T extends string>(x: T): T => x;",
            "export const run = <T extends number>(x: T): T => x;",
            False,
        ),
        (
            "local_export_signature",
            "function run(x: string) {} export { run };",
            "function run(x: number) {} export { run };",
            False,
        ),
        (
            "local_export_removed",
            "function run(x: string) {} export { run };",
            "function run(x: string) {}",
            False,
        ),
        ("named_reexport_removed", 'export { run } from "./impl";', "", False),
        (
            "overload_changed",
            "export function run(x: string): string; export function run(x: any): any { return x; }",
            "export function run(x: number): number; export function run(x: any): any { return x; }",
            False,
        ),
        ("object_removed", "export const settings = { retries: 2 };", "", False),
    ]
    for name, before, after, control in pairs:
        result = change.surface_delta(before, after, TYPESCRIPT, "src/api.ts")
        visible = (
            result is None
            or bool(result.get("unknown"))
            or any(
                names for part in ("added", "removed", "changed") for names in result[part].values()
            )
        )
        record(
            name, "An exported API change is reported or marked unknown.", visible, result, control
        )
    surface = parse_surface("export class Item { #hidden(): void {} public visible(): void {} }")
    methods = surface["classes"][0]["methods"] if surface else []
    record(
        "private_method",
        "A JavaScript private method is excluded from the public API.",
        not any("#hidden" in method for method in methods),
        methods,
    )


def export_cases(root: Path, compiler: str) -> None:
    project(
        root,
        {
            "src/a.ts": 'export { run } from "./middle";',
            "src/middle.ts": 'export { run } from "./z";',
            "src/z.ts": "export function run(): void {}",
            "src/index.ts": 'export { run } from "./a";',
        },
    )
    truth = oracle(root, compiler, exports=["src/index.ts"])
    facts = extract.build(config.load(root))
    names = facts["components"]["web.index"]["names"]
    record(
        "reexport_chain",
        "A function re-exported through barrels remains a function and an entry point.",
        names == [{"name": "run", "kind": "function", "reexport_of": "web.a"}]
        and any(e["name"] == "run" for e in facts["entry_points"]),
        {"compiler": truth, "names": names, "entries": facts["entry_points"]},
    )
    write(
        root,
        {
            "src/a.ts": "export function run(): void {}",
            "src/middle.ts": "export function run(): void {}",
            "src/index.ts": 'export * from "./a"; export * from "./middle";',
        },
    )
    facts = extract.build(config.load(root))
    truth = oracle(root, compiler, exports=["src/index.ts"])
    record(
        "star_ambiguity",
        "Conflicting star exports produce an explicit uncertainty.",
        bool(extract.unknown_fact_lines(facts)),
        {
            "compiler": truth,
            "names": facts["components"]["web.index"]["names"],
            "unknown": extract.unknown_fact_lines(facts),
        },
    )


def test_cases(root: Path) -> None:
    project(
        root,
        {
            "src/value.ts": "export const value = 1;",
            "tests/value.test.ts": 'import { value } from "../src/value";\n'
            + "\n".join(f'test("case {i}", () => value);' for i in range(30)),
        },
    )
    facts = extract.build(config.load(root))
    record(
        "test_count_cap",
        "All 30 distinct tests count, even when the displayed list is capped at 25.",
        facts["components"]["web.value"]["tests_total"] == 30,
        {key: facts["components"]["web.value"][key] for key in ("tests_total", "tests")},
    )
    names = test_names(
        'test.only("focused", () => {}); it.concurrent("parallel", () => {}); test("ordinary", () => {});'
    )
    record(
        "test_modifiers",
        "Common test modifiers retain their literal test names.",
        set(names) == {"focused", "parallel", "ordinary"},
        names,
    )


def import_form_cases(root: Path, compiler: str) -> None:
    forms = {
        "dynamic_import": 'export async function load() { return import("./value"); }',
        "require_import": 'import value = require("./value"); export const result = value;',
    }
    for name, source in forms.items():
        folder = root / name
        project(
            folder,
            {"src/entry.ts": source, "src/value.ts": "export const value = 1;"},
            {"compilerOptions": {"module": "commonjs", "target": "es2022"}},
        )
        facts = extract.build(config.load(folder))
        truth = oracle(
            folder, compiler, imports=[{"specifier": "./value", "importer": "src/entry.ts"}]
        )
        uses = facts["components"]["web.entry"]["uses"]
        record(
            name,
            "A literal dependency is retained or explicitly marked unknown.",
            "web.value" in uses or bool(extract.unknown_fact_lines(facts)),
            {"compiler": truth, "uses": uses, "unknown": extract.unknown_fact_lines(facts)},
        )


def drift_case(root: Path) -> None:
    opts = {
        "module": "esnext",
        "moduleResolution": "bundler",
        "baseUrl": ".",
        "paths": {"@value": ["src/a.ts"]},
    }
    project(
        root,
        {
            "src/a.ts": "export const value = 1;",
            "src/b.ts": "export const value = 2;",
            "src/entry.ts": 'import { value } from "@value"; export const result = value;',
        },
        {"compilerOptions": opts},
    )
    before = extract.build(config.load(root))
    opts["paths"] = {"@value": ["src/b.ts"]}
    write(root, {"tsconfig.json": json.dumps({"compilerOptions": opts})})
    after = extract.build(config.load(root))
    drift = extract.drift(after, before)
    record(
        "config_dependency_freshness",
        "A tsconfig alias change invalidates facts whose import target changed.",
        bool(drift),
        {
            "before": before["components"]["web.entry"]["uses"],
            "after": after["components"]["web.entry"]["uses"],
            "drift": drift,
        },
    )


def input_case(root: Path, compiler: str) -> None:
    project(
        root,
        {
            "src/cli.ts": 'import { value } from "../shared/value"; console.log(value);',
            "shared/value.ts": "export const value = 1;",
            "package.json": '{"name":"web","devDependencies":{"typescript":"5.9.3"},"bin":{"correct":"out/src/cli.js","wrong":"out/cli.js"}}',
        },
        {
            "include": ["src"],
            "compilerOptions": {"outDir": "out", "module": "commonjs", "target": "es2022"},
        },
    )
    truth = oracle(root, compiler)
    facts = extract.build(config.load(root))
    bins = {e["name"]: e["module"] for e in facts["entry_points"] if e["kind"] == "console_script"}
    record(
        "imported_input_rootdir",
        "TypeScript 5 emit root includes files brought into the program by imports.",
        bins == {"correct": "web.cli"},
        {"compiler": truth, "bins": bins, "issues": facts["entry_point_issues"]},
    )


def integration_cases(root: Path) -> None:
    project(
        root,
        {
            "src/api.ts": "export default function run(x: string): void {}",
            "src/caller.ts": 'import run from "./api"; export function call(): void { run("x"); }',
        },
    )
    git(root, "init", "-q")
    base = commit(root)
    write(root, {"src/api.ts": "export default function run(x: number): void {}"})
    commit(root)
    cfg = config.load(root)
    model = model_of(card("API", "web.api"), card("Caller", "web.caller"))
    result = change.compute(cfg, model, base, extract.build(cfg))
    record(
        "default_export_change_wire",
        "An imported default function's signature change is identified on the wire.",
        bool(result["artifacts"]),
        {
            "artifacts": sorted(result["artifacts"]),
            "direct": sorted(result["direct"]),
            "adjacent": sorted(result["adjacent"]),
        },
    )
    write(
        root,
        {
            "src/api.ts": "export interface Item { id: string }",
            "src/caller.ts": 'import type { Item } from "./api"; export const item: Item = { id: "x" };',
        },
    )
    facts = extract.build(cfg)
    model = model_of(
        card("API", "web.api"),
        card("Caller", "web.caller"),
        flows=(Flow("API", "Caller", "data", "Item"),),
    )
    state = evidence.of_model(model, Meaning(plain={}), facts)[("API", "Caller")]
    record(
        "type_only_flow_evidence",
        "An erased type import is distinguished from evidence of a runtime data flow.",
        state.state != "observed",
        {"uses": facts["components"]["web.caller"]["uses"], "evidence": state.says},
    )
    workflow = scaffold.files("web", "web", [("src", "web")], language="typescript")[
        ".github/workflows/systemap.yml"
    ]
    commands = [line.strip() for line in workflow.splitlines() if "uvx --from" in line]
    record(
        "typescript_ci_extra",
        "Generated TypeScript CI installs the TypeScript parser extra.",
        all("systemap[typescript]" in command for command in commands),
        commands,
    )


def freshness_cli_case(root: Path) -> None:
    shutil.copytree(ROOT / "tests/fixtures/typescript-app", root)
    client = (root / "src/client.ts").read_text()
    cli = root / "src/cli.ts"
    cli.write_text(cli.read_text() + client)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        refreshed = cli_main(["--root", str(root), "refresh"])
    before = extract.build(config.load(root))
    settings = json.loads((root / "tsconfig.json").read_text())
    # Put the exact match first so this case isolates freshness from alias ordering.
    settings["compilerOptions"]["paths"] = {"@/client": ["src/cli.ts"], "@/*": ["src/*"]}
    write(root, {"tsconfig.json": json.dumps(settings)})
    after = extract.build(config.load(root))
    with contextlib.redirect_stdout(output):
        checked = cli_main(["--root", str(root), "extract", "--check"])
    record(
        "config_freshness_cli",
        "The extract freshness gate fails after a dependency target changes via tsconfig.",
        refreshed == 0 and checked == 1,
        {
            "refresh_exit": refreshed,
            "check_exit": checked,
            "before": before["components"]["acme.web.service"]["uses"],
            "after": after["components"]["acme.web.service"]["uses"],
            "output": output.getvalue(),
        },
    )


def unknown_control(root: Path) -> None:
    project(root, {"src/broken.ts": "export function broken( {"})
    facts = extract.build(config.load(root))
    record(
        "parse_unknown_control",
        "An unparsable TypeScript module is retained and flagged.",
        "web.broken" in facts["components"] and bool(extract.unknown_fact_lines(facts)),
        extract.unknown_fact_lines(facts),
        True,
    )


def main() -> None:
    compiler = str(Path(sys.argv[1]).resolve())
    surface_cases()
    with tempfile.TemporaryDirectory(prefix="systemap-ts-review-") as tmp:
        root = Path(tmp)
        resolution_cases(root / "resolution", compiler)
        export_cases(root / "exports", compiler)
        test_cases(root / "tests")
        import_form_cases(root / "imports", compiler)
        drift_case(root / "drift")
        input_case(root / "inputs", compiler)
        integration_cases(root / "integration")
        freshness_cli_case(root / "freshness_cli")
        unknown_control(root / "unknown")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()
    result = {
        "revision": revision,
        "compiler_path": compiler,
        "compiler_sha256": hashlib.sha256(Path(compiler).read_bytes()).hexdigest(),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "src/systemap").glob("*.py"))
        },
        "cases": ROWS,
        "note": "Targeted contracts, not an estimate of production accuracy.",
    }
    path = HERE / "results/typescript-accuracy-review.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    for row in ROWS:
        print(f"{'PASS' if row['met'] else 'GAP ':4} {row['case']}")
    print(f"{sum(row['met'] for row in ROWS)}/{len(ROWS)} contracts met; {path}")


if __name__ == "__main__":
    main()
