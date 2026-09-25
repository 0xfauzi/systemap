from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import change, config, delta, extract, history, nest, typescript_config
from systemap.cli import main
from systemap.typescript import TYPESCRIPT, parse_surface
from systemap.typescript import test_names as names_of_tests

TREE = {
    "package.json": '{"name":"@acme/web","bin":{"web":"src/cli.ts"}}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": (
        'language = "typescript"\ntests_dir = "tests"\n[package_roots]\n"src" = "web"\n'
    ),
    "src/index.ts": 'export { serve } from "./service";\n',
    "src/types.ts": "export interface User { name: string; save(): void }\n",
    "src/client.ts": "export function fetchUser(id: string): User { return { id } as User }\n",
    "src/service.ts": (
        "/** Serve one user. */\n"
        'import type { User } from "./types";\n'
        'import { fetchUser } from "./client";\n'
        'import { z } from "zod";\n'
        "export const LIMIT = 3;\n"
        "export async function serve(id: string): Promise<User> { return fetchUser(id) }\n"
        "export class ServeError extends Error { public explain(): string { return z.string() } }\n"
        "const hidden = 1;\n"
    ),
    "src/cli.ts": "export function main(): void {}\n",
    "tests/service.test.ts": (
        'import { serve } from "../src/service";\n'
        'describe("service", () => { test("serves a user", () => serve("1")) });\n'
    ),
}


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def test_typescript_extracts_surface_imports_tests_and_entry_points(tmp_path: Path) -> None:
    write_tree(tmp_path, TREE)
    cfg = config.load(tmp_path)
    assert cfg.language == "typescript"
    assert extract.language_for(cfg) is TYPESCRIPT

    facts = extract.build(cfg)
    assert sorted(facts["components"]) == [
        "web.cli",
        "web.client",
        "web.index",
        "web.service",
        "web.types",
    ]
    service = facts["components"]["web.service"]
    assert service["docstring"] == "Serve one user."
    assert service["functions"] == [
        {"name": "serve", "signature": "async function serve(id: string): Promise<User>"}
    ]
    assert service["classes"] == []
    assert service["errors"] == [{"name": "ServeError", "methods": ["public explain(): string"]}]
    assert service["constants"] == [{"name": "LIMIT", "value": "3"}]
    assert service["uses"] == {"web.client": ["fetchUser"], "web.types": ["User"]}
    assert service["external"] == ["zod"]
    assert service["tests"] == ["serves a user"]
    assert service["tests_primary"] == 1

    assert facts["components"]["web.index"]["names"] == [
        {"name": "serve", "kind": "function", "reexport_of": "web.service"}
    ]
    assert facts["entry_points"] == [
        {"kind": "console_script", "name": "web", "module": "web.cli", "target": ""},
        {"kind": "public_function", "name": "serve", "module": "web.index", "target": ""},
    ]


def test_typescript_roots_are_discovered_from_package_metadata(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": (
                '{"name":"@acme/web","exports":{".":"./src/index.ts","./api":"./src/api.ts"}}'
            ),
            "tsconfig.json": '{"compilerOptions":{}}',
            "systemap.toml": 'language = "typescript"\n',
            "src/api.ts": "export function request(): void {}\n",
            "src/index.ts": "export const app = () => 1;\n",
        },
    )
    cfg = config.load(tmp_path)
    assert cfg.package_roots == (("src", "acme.web"),)
    facts = extract.build(cfg)
    assert sorted(facts["components"]) == ["acme.web.api", "acme.web.index"]
    assert facts["entry_points"] == [
        {
            "kind": "public_function",
            "name": "request",
            "module": "acme.web.api",
            "target": "",
        },
        {
            "kind": "public_function",
            "name": "app",
            "module": "acme.web.index",
            "target": "",
        },
    ]


def test_init_detects_a_typescript_repository(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/index.ts": "export const app = () => 1;\n",
        },
    )
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    text = (tmp_path / "systemap.toml").read_text(encoding="utf-8")
    assert 'language = "typescript"' in text
    assert '[package_roots]\n"src" = "web"' in text
    assert sorted(extract.build(config.load(tmp_path))["components"]) == ["web.index"]


def test_typescript_surface_and_change_use_the_same_parser() -> None:
    before = "export function read(value: string): string { return value }\n"
    after = "export function read(value: number): string { return String(value) }\n"
    surface = parse_surface(before)
    assert surface is not None
    assert surface["functions"] == [
        {"name": "read", "signature": "function read(value: string): string"}
    ]
    assert change.surface_delta(before, after, TYPESCRIPT) == {
        "added": {"operations": [], "types": [], "refusals": [], "constants": []},
        "removed": {"operations": [], "types": [], "refusals": [], "constants": []},
        "changed": {"operations": ["read"], "types": [], "refusals": [], "constants": []},
    }


def test_typescript_test_names_are_literal_and_nested() -> None:
    assert names_of_tests(
        'test("one", () => {}); describe("group", () => { it("two", () => {}) });'
    ) == ["one", "two"]
    assert names_of_tests("test(name, () => {})") == []


def test_typescript_exports_are_named_or_explicitly_unknown() -> None:
    surface = parse_surface(
        "const g = () => 1;\n"
        "export { g };\n"
        "export const { p, q: renamed, ...rest } = source;\n"
        "export abstract class Base {}\n"
        "export namespace Tools {}\n"
        "export declare function declared(value: string): void;\n"
        'export * from "./more";\n'
        'export * as more from "./more";\n'
    )
    assert surface is not None
    names = {entry["name"]: entry["kind"] for entry in surface["names"]}
    assert names == {
        "g": "function",
        "p": "object",
        "renamed": "object",
        "rest": "object",
        "Base": "class",
        "Tools": "object",
        "declared": "function",
        "*": "reexport",
        "more": "object",
    }
    assert surface["unknown"] == []

    default_function = parse_surface("export default (value: string) => value;")
    assert default_function is not None
    assert default_function["names"] == [{"name": "default", "kind": "function"}]
    anonymous_function = parse_surface(
        "export default function (value: string): string { return value; }"
    )
    assert anonymous_function is not None
    assert anonymous_function["names"] == [{"name": "default", "kind": "function"}]
    default_expression = parse_surface("export default { answer: 42 };")
    assert default_expression is not None
    assert default_expression["names"] == [{"name": "default", "kind": "unknown"}]
    assert default_expression["unknown"]


def test_typescript_star_exports_expand_public_names(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": ('language = "typescript"\n[package_roots]\n"src" = "web"\n'),
            "src/index.ts": 'export * from "./more";\nexport * as more from "./more";\n',
            "src/more.ts": "export function available(): void {}\nexport const value = 1;\n",
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert facts["components"]["web.index"]["names"] == [
        {"name": "available", "kind": "function", "reexport_of": "web.more"},
        {"name": "value", "kind": "object", "reexport_of": "web.more"},
        {"name": "more", "kind": "object", "reexport_of": "web.more"},
    ]


def test_typescript_jsonc_extends_aliases_and_dist_targets(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": (
                '{"name":"web","bin":{"web":"dist/cli.js",'
                '"missing":"dist/missing.js"},"exports":{".":{"types":"./dist/index.d.ts",'
                '"import":"./dist/index.js"},"./features/*":"./dist/features/*.js"}}'
            ),
            "tsconfig.base.json": (
                "{\n"
                "  // Shared compiler settings.\n"
                '  "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]},\n'
                '    "rootDir": "src", "outDir": "dist",},\n'
                "}\n"
            ),
            "tsconfig.json": (
                "{\n"
                '  "extends": "./tsconfig.base.json",\n'
                "  /* Keep the local options empty. */\n"
                '  "compilerOptions": {},\n'
                "}\n"
            ),
            "systemap.toml": 'language = "typescript"\n',
            "src/index.ts": (
                'import { serve } from "@/service";\nexport function api(): void { serve(); }\n'
            ),
            "src/service.ts": "export function serve(): void {}\n",
            "src/cli.ts": "export function main(): void {}\n",
        },
    )
    cfg = config.load(tmp_path)
    facts = extract.build(cfg)
    assert facts["components"]["web.index"]["uses"] == {"web.service": ["serve"]}
    assert facts["entry_points"] == [
        {"kind": "console_script", "name": "web", "module": "web.cli", "target": ""},
        {"kind": "public_function", "name": "api", "module": "web.index", "target": ""},
    ]
    assert {issue["kind"] for issue in facts["entry_point_issues"]} == {
        "package_bin",
        "package_export",
    }
    assert facts["test_file_issues"] == []
    assert set(facts) == extract.fields_of("facts")
    assert all(
        set(record) == extract.fields_of("module") for record in facts["components"].values()
    )


def test_typescript_parser_failure_is_retained_as_unknown_surface(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "src/broken.ts": "export function broken( {",
        },
    )
    facts = extract.build(config.load(tmp_path))
    issue = facts["components"]["web.broken"]["unknown"][0]
    assert "could not be parsed" in issue["reason"]
    assert extract.unknown_fact_lines(facts) == [
        f"unknown surface: module web.broken (src/broken.ts:{issue['line']}): {issue['reason']}"
    ]


def test_typescript_fixture_resolves_aliases_tsx_and_runs_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "typescript-app"
    shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)

    cfg = config.load(tmp_path)
    facts = extract.build(cfg)
    service = facts["components"]["acme.web.service"]
    assert service["uses"] == {"acme.web.client": ["User", "fetchUser"]}
    assert service["external"] == ["zod"]
    assert service["tests"] == ["serves a user"]
    assert facts["components"]["acme.web.view"]["functions"] == [
        {"name": "UserView", "signature": "function UserView(): JSX.Element"}
    ]
    assert facts["components"]["acme.web.index"]["names"] == [
        {"name": "serve", "kind": "function", "reexport_of": "acme.web.service"},
        {"name": "default", "kind": "function", "reexport_of": "acme.web.service"},
        {"name": "UserView", "kind": "function", "reexport_of": "acme.web.view"},
    ]

    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
    assert (tmp_path / "docs/map/map.json").is_file()
    assert (tmp_path / "docs/map/index.html").is_file()
    capsys.readouterr()


def test_typescript_delta_and_history_read_committed_trees(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "typescript-app"
    shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
    write_tree(tmp_path, {"src/legacy.ts": "export function legacy(): void {}\n"})
    model = tmp_path / "map/model.py"
    model.write_text(
        model.read_text(encoding="utf-8").replace(
            '            "acme.web.index",',
            '            "acme.web.index",\n            "acme.web.legacy",',
        ),
        encoding="utf-8",
    )
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD")

    (tmp_path / "src/cli.ts").rename(tmp_path / "src/command.ts")
    (tmp_path / "src/legacy.ts").unlink()
    write_tree(
        tmp_path,
        {
            "src/jobs.ts": "export function runJob(): void {}\n",
            "src/service.ts": (
                'import { fetchUser, type User } from "@/client";\n'
                "export function serve(id: number): User { return fetchUser(String(id)); }\n"
            ),
            "tests/service.test.ts": (
                'import { serve } from "@/service";\n'
                'test("serves a user", () => serve(1));\n'
                'test("serves another user", () => serve(2));\n'
            ),
            "package.json": '{"name":"@acme/web","bin":{"web":"src/command.ts"}}',
        },
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "head")
    head = git(tmp_path, "rev-parse", "HEAD")

    cfg = config.load(tmp_path)
    base_facts = delta.facts_at(cfg, base)
    head_facts = history.facts_at(cfg, head)
    assert base_facts["components"]["acme.web.service"]["functions"][0]["signature"] == (
        "function serve(id: string): User"
    )
    assert head_facts["components"]["acme.web.service"]["functions"][0]["signature"] == (
        "function serve(id: number): User"
    )
    assert head_facts["components"]["acme.web.service"]["tests"] == [
        "serves a user",
        "serves another user",
    ]
    assert head_facts["entry_points"][0]["module"] == "acme.web.command"
    assert (history.cache_dir(cfg) / f"{head}.json").is_file()

    assert main(["--root", str(tmp_path), "delta", "--base", base, "--brief"]) == 1
    out = capsys.readouterr().out
    assert "moved: acme.web.cli -> acme.web.command (same content)" in out
    assert "added: acme.web.jobs, claimed by no card" in out
    assert "removed: acme.web.legacy" in out


def test_typescript_change_attributes_changed_tsx_tests(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "typescript-app"
    shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
    test_path = tmp_path / "tests/service.test.ts"
    tsx_path = test_path.with_suffix(".tsx")
    test_path.rename(tsx_path)
    tsx_path.write_text(
        'import { serve } from "@/service";\n'
        'test("serves a user", () => <main>{serve("1").id}</main>);\n',
        encoding="utf-8",
    )
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    tsx_path.write_text(
        tsx_path.read_text(encoding="utf-8")
        + 'test("serves another user", () => <main>{serve("2").id}</main>);\n',
        encoding="utf-8",
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "head")

    cfg = config.load(tmp_path)
    found = change.compute(cfg, nest.load(cfg).top.model, "HEAD~1", extract.build(cfg))
    assert found["direct"] == {"Application"}
    assert found["per_component"]["Application"]["surface"]["tests_added"] == [
        "serves another user"
    ]


def test_configured_typescript_test_patterns_match_extract_and_delta(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "typescript-app"
    shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
    settings = tmp_path / "systemap.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace(
            'tests_dir = "tests"\n',
            'tests_dir = "tests"\ntest_patterns = ["src/checks/**/*.ts"]\n',
        ),
        encoding="utf-8",
    )
    test_path = tmp_path / "src/checks/service_check.ts"
    test_path.parent.mkdir(parents=True)
    test_path.write_text(
        'import { serve } from "../service";\ntest("checks service", () => serve("one"));\n',
        encoding="utf-8",
    )
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD")

    test_path.write_text(
        test_path.read_text(encoding="utf-8")
        + 'test("checks service again", () => serve("two"));\n',
        encoding="utf-8",
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "add a configured test")

    cfg = config.load(tmp_path)
    facts = extract.build(cfg)
    assert "acme.web.checks.service_check" not in facts["components"]
    assert "checks service" in facts["components"]["acme.web.service"]["tests"]
    found = change.compute(cfg, nest.load(cfg).top.model, base, facts)
    assert found["direct"] == {"Application"}
    assert found["per_component"]["Application"]["surface"]["tests_added"] == [
        "checks service again"
    ]


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
    assert "both Python and TypeScript source found" in capsys.readouterr().err


def test_typescript_discovers_nested_source_and_refuses_module_id_collisions(
    tmp_path: Path,
) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": '{"name":"web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "systemap.toml": 'language = "typescript"\n',
            "src/nested/one.ts": "export const ONE = 1;",
        },
    )
    assert typescript_config.discover_typescript_roots(tmp_path) == [("src", "web")]

    write_tree(tmp_path, {"src/some-file.ts": "", "src/some_file.ts": ""})
    with pytest.raises(config.ConfigError, match="module id web.some_file is shared"):
        extract.build(config.load(tmp_path))
