from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import change, config, extract
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
        {"kind": "console_script", "name": "web", "module": "web.cli", "target": ""}
    ]


def test_typescript_roots_are_discovered_from_package_metadata(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": '{"name":"@acme/web"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "systemap.toml": 'language = "typescript"\n',
            "src/index.ts": "export const app = () => 1;\n",
        },
    )
    cfg = config.load(tmp_path)
    assert cfg.package_roots == (("src", "acme.web"),)
    assert sorted(extract.build(cfg)["components"]) == ["acme.web.index"]


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


def test_typescript_parse_failure_is_not_an_empty_module(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "src/broken.ts": "export function broken( {",
        },
    )
    with pytest.raises(config.ConfigError, match="src/broken.ts: could not parse TypeScript"):
        extract.build(config.load(tmp_path))


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
    assert config.discover_typescript_roots(tmp_path) == [("src", "web")]

    write_tree(tmp_path, {"src/some-file.ts": "", "src/some_file.ts": ""})
    with pytest.raises(config.ConfigError, match="module id web.some_file is shared"):
        extract.build(config.load(tmp_path))
