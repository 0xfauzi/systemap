"""Source extraction gives the same facts for the same committed source on each computer.

These contracts cover the folders above a repository, source folders with build names,
facts without modules, newline forms, interpreter and npm package differences, text that
is not UTF-8, and a UTF-8 byte order mark.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, TINY_PACKAGE, init_two_cards, write_tree

from systemap import (
    check,
    config,
    extract,
    judgement,
    judgement_evidence,
    nest,
    source_facts,
    typescript_roots,
)
from systemap.cli import main

LATIN_1 = "# -*- coding: latin-1 -*-\nNAME = '\xe9t\xe9'\n".encode("latin-1")
BOM = b"\xef\xbb\xbf"

TYPESCRIPT_TREE = {
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": (
        'language = "typescript"\ntests_dir = "tests"\n[package_roots]\n"src" = "web"\n'
    ),
    "src/service.ts": "export function serve(): number { return 1 }\n",
    "src/cli.ts": 'import { serve } from "./service";\nexport const main = () => serve();\n',
    "tests/service.test.ts": (
        'import { serve } from "../src/service";\n'
        'describe("service", () => { test("serves", () => serve()) });\n'
    ),
}


NEWLINE_FILES = ("pkg/reader.py", "pkg/writer.py", "map/model.py", "pyproject.toml")


def _lf(path: Path) -> None:
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def _crlf(path: Path) -> None:
    _lf(path)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))


# ---- folder names: only the folders below a package root can remove source ----------


@pytest.mark.parametrize("parent", ["build", "dist", ".venv", "node_modules"])
def test_folder_above_the_repository_does_not_remove_python_modules(
    tmp_path: Path, parent: str
) -> None:
    """Acceptance: a repository below a folder with a skip name keeps all 3 modules."""
    root = tmp_path / parent / "project"
    write_tree(root, TINY_PACKAGE)
    write_tree(root, {"tests/test_reader.py": "from pkg.reader import read\ndef test_a(): ...\n"})
    facts = extract.build(config.load(root))
    assert sorted(facts["components"]) == ["pkg", "pkg.reader", "pkg.writer"]
    assert facts["components"]["pkg.reader"]["tests_total"] == 1


def test_package_named_build_keeps_its_modules(tmp_path: Path) -> None:
    """Acceptance: the pypa/build layout gives its modules, and a .venv below it does not."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": '[package_roots]\n"src/build" = "build"\n',
            "src/build/__init__.py": "",
            "src/build/env.py": "def make(): ...\n",
            "src/build/.venv/lib/site.py": "def other(): ...\n",
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert sorted(facts["components"]) == ["build", "build.env"]


def test_folder_above_the_repository_does_not_remove_typescript_modules(
    tmp_path: Path,
) -> None:
    """Acceptance: a TypeScript repository below `build` has its modules, tests and root."""
    root = tmp_path / "build" / "web"
    write_tree(root, TYPESCRIPT_TREE)
    facts = extract.build(config.load(root))
    assert sorted(facts["components"]) == ["web.cli", "web.service"]
    assert facts["components"]["web.service"]["tests_total"] == 1
    assert typescript_roots.discover_typescript_roots(root) == [("src", "web")]


def test_typescript_source_folders_named_build_or_dist_are_source(tmp_path: Path) -> None:
    """Acceptance: tsc reads `build` and `dist` source folders. It skips outDir and
    node_modules, and the extractor does the same.
    """
    write_tree(
        tmp_path,
        {
            "package.json": '{"name":"tool"}',
            "tsconfig.json": '{"compilerOptions":{"outDir":"out"}}',
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"." = "tool"\n',
            "cli.ts": 'import { compile } from "./commands/build";\nexport const run = compile;\n',
            "commands/build/index.ts": "export function compile(): void {}\n",
            "dist/pack.ts": "export const pack = 1;\n",
            "out/cli.ts": "export const copied = 1;\n",
            "node_modules/lib/index.ts": "export const lib = 1;\n",
            "commands/build/index.test.ts": (
                'import { compile } from "./index";\ntest("compiles", () => compile());\n'
            ),
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert sorted(facts["components"]) == [
        "tool.cli",
        "tool.commands.build.index",
        "tool.dist.pack",
    ]
    assert facts["components"]["tool.cli"]["imports"] == ["tool.commands.build.index"]
    assert facts["components"]["tool.commands.build.index"]["tests_total"] == 1


@pytest.mark.parametrize("out_dir", [".", ".."])
def test_typescript_out_dir_that_contains_the_source_removes_nothing(
    tmp_path: Path, out_dir: str
) -> None:
    root = tmp_path / "web"
    write_tree(root, TYPESCRIPT_TREE)
    write_tree(root, {"tsconfig.json": json.dumps({"compilerOptions": {"outDir": out_dir}})})
    facts = extract.build(config.load(root))
    assert sorted(facts["components"]) == ["web.cli", "web.service"]
    assert facts["components"]["web.service"]["tests_total"] == 1


# ---- facts without modules -------------------------------------------------------------


def test_check_refuses_facts_without_modules_for_a_model_with_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: a package root without source makes check and refresh give exit code 1."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    settings = tmp_path / "systemap.toml"
    text = settings.read_text(encoding="utf-8")
    settings.write_text(text.replace('"pkg" = "pkg"', '"docs" = "pkg"'), encoding="utf-8")
    write_tree(tmp_path, {"docs/README.md": "No source.\n"})
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "refresh"]) == 1
    assert main(["--root", str(tmp_path), "check"]) == 1
    out = capsys.readouterr().out
    assert "The facts contain no source modules." in out
    assert "Reader has a module claim for pkg.reader, which is missing from the facts." in out


def test_entry_check_without_facts_is_still_empty(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    model = nest.load(config.load(tmp_path)).maps[0].model
    assert check.check_entry(model, {}) == []
    lines = check.check_entry(model, {"version": extract.FORMAT, "components": {}})
    assert lines[0].startswith("The facts contain no source modules.")


# ---- newline forms ---------------------------------------------------------------------


def test_crlf_checkout_keeps_answer_evidence_and_provenance(tmp_path: Path) -> None:
    """Acceptance: CRLF text gives the same digests as LF text, and LF digests stay the
    plain SHA-256 of the file bytes.
    """
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    write_tree(tmp_path, {"pyproject.toml": '[project]\nname = "pkg"\n'})
    init_two_cards(tmp_path, "--no-ci")
    for name in NEWLINE_FILES:
        _lf(tmp_path / name)
    cfg = config.load(tmp_path)
    tree = nest.load(cfg)
    facts = extract.build(cfg)
    lines = judgement.run_tree(tree, facts)
    before = judgement.evidence_for_tree(tree, facts, tmp_path, lines)
    record = facts["components"]["pkg.reader"]
    plain = hashlib.sha256((tmp_path / "pkg/reader.py").read_bytes()).hexdigest()
    assert judgement_evidence._source_hash(tmp_path, record) == plain
    pyproject = hashlib.sha256((tmp_path / "pyproject.toml").read_bytes()).hexdigest()
    assert facts["provenance"]["files"]["pyproject.toml"] == pyproject
    for name in NEWLINE_FILES:
        _crlf(tmp_path / name)
    assert (tmp_path / "pkg/reader.py").read_bytes().count(b"\r\n") == 2
    tree = nest.load(config.load(tmp_path))
    fresh = extract.build(config.load(tmp_path))
    assert judgement.evidence_for_tree(tree, facts, tmp_path, lines) == before
    assert fresh["provenance"] == facts["provenance"]
    assert extract.drift(fresh, facts) == []


def test_crlf_checkout_passes_extract_check_and_check(tmp_path: Path) -> None:
    """Acceptance: after refresh, a CRLF copy of the same text passes the CI commands."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    write_tree(tmp_path, {"pyproject.toml": '[project]\nname = "pkg"\n'})
    init_two_cards(tmp_path, "--no-ci")
    cfg = config.load(tmp_path)
    tree = nest.load(cfg)
    lines = judgement.run_tree(tree, extract.build(cfg))
    item = next(line for line in lines if line.startswith("single module: Reader"))
    evidence = judgement.evidence_for_tree(tree, extract.build(cfg), tmp_path, [item])[item]
    settings = tmp_path / "systemap.toml"
    answer = f'answered = [{{ item = "{item}", reason = "A test.", evidence = "{evidence}" }}]'
    settings.write_text(
        settings.read_text(encoding="utf-8") + f"\n[judgement]\n{answer}\n", encoding="utf-8"
    )
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
    for name in NEWLINE_FILES:
        _crlf(tmp_path / name)
    assert main(["--root", str(tmp_path), "extract", "--check"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0


# ---- values that are local to one computer ----------------------------------------------


def test_python_minor_version_alone_is_not_an_input_change(tmp_path: Path) -> None:
    """Acceptance: facts from another Python minor version agree when the facts agree."""
    write_tree(tmp_path, TINY_PACKAGE)
    fresh = extract.build(config.load(tmp_path))
    stored = copy.deepcopy(fresh)
    stored["provenance"]["parser"] = "3.99"
    assert extract.drift(fresh, stored) == []
    stored["components"]["pkg.reader"]["names"] = []
    assert extract.drift(fresh, stored) == [
        "derived facts changed since the map was built: pkg.reader"
    ]
    changed = copy.deepcopy(fresh)
    changed["provenance"]["settings"] = "other settings"
    assert "extraction inputs changed since the map was built" in extract.drift(fresh, changed)


def test_npm_tsconfig_package_alone_is_not_an_input_change(tmp_path: Path) -> None:
    """Acceptance: a clone without node_modules agrees with facts made with node_modules
    when the extracted facts agree.
    """
    write_tree(tmp_path, TYPESCRIPT_TREE)
    write_tree(
        tmp_path,
        {
            "tsconfig.json": '{"extends":"@tsconfig/node20/tsconfig.json"}',
            "node_modules/@tsconfig/node20/tsconfig.json": '{"compilerOptions":{"strict":true}}',
            "node_modules/typescript/package.json": '{"version":"5.9.3"}',
        },
    )
    with_packages = extract.build(config.load(tmp_path))
    assert with_packages["config_issues"] == []
    for name in ("@tsconfig/node20/tsconfig.json", "typescript/package.json"):
        (tmp_path / "node_modules" / name).unlink()
    without = extract.build(config.load(tmp_path))
    assert without["config_issues"] != []
    assert extract.drift(without, with_packages) == []
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions":{}}', encoding="utf-8")
    edited = extract.build(config.load(tmp_path))
    assert "extraction inputs changed since the map was built" in extract.drift(
        edited, with_packages
    )


def test_npm_tsconfig_package_with_paths_is_a_facts_change(tmp_path: Path) -> None:
    """Acceptance: if the npm package changes the import graph, the facts disagree."""
    write_tree(tmp_path, TYPESCRIPT_TREE)
    write_tree(
        tmp_path,
        {
            "tsconfig.json": '{"extends":"@acme/tsconfig/base.json"}',
            "node_modules/@acme/tsconfig/base.json": json.dumps(
                {"compilerOptions": {"baseUrl": "${configDir}", "paths": {"@/*": ["src/*"]}}}
            ),
            "src/cli.ts": 'import { serve } from "@/service";\nexport const main = serve;\n',
        },
    )
    with_packages = extract.build(config.load(tmp_path))
    assert with_packages["components"]["web.cli"]["imports"] == ["web.service"]
    (tmp_path / "node_modules/@acme/tsconfig/base.json").unlink()
    without = extract.build(config.load(tmp_path))
    assert "derived facts changed since the map was built: web.cli" in extract.drift(
        without, with_packages
    )


# ---- text that is not UTF-8, and a byte order mark --------------------------------------


def test_python_module_that_is_not_utf8_keeps_a_read_problem(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    (tmp_path / "pkg/latin.py").write_bytes(LATIN_1)
    write_tree(
        tmp_path, {"tests/test_reader.py": "from pkg.reader import read\ndef test_a(): ...\n"}
    )
    (tmp_path / "tests/test_latin.py").write_bytes(LATIN_1)
    facts = extract.build(config.load(tmp_path))
    problem = facts["components"]["pkg.latin"]["parse_error"]
    assert problem["reason"] == "source could not be read: UnicodeDecodeError"
    assert facts["components"]["pkg.reader"]["tests_total"] == 1
    assert "source inventory unresolved: pkg.latin (pkg/latin.py)" in (
        source_facts.inventory_issue_lines(facts)
    )


def test_spec_file_that_is_not_utf8_gives_no_sections(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    write_tree(tmp_path, {"systemap.toml": 'spec_path = "docs/design.md"\n'})
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs/design.md").write_bytes("## \xc9t\xe9\n".encode("latin-1"))
    assert extract.build(config.load(tmp_path))["spec_sections"] == []


def test_typescript_files_that_are_not_utf8_keep_a_read_problem(tmp_path: Path) -> None:
    write_tree(tmp_path, TYPESCRIPT_TREE)
    (tmp_path / "src/latin.ts").write_bytes("// \xe9t\xe9\nexport const a = 1;\n".encode("latin-1"))
    (tmp_path / "tests/latin.test.ts").write_bytes("// \xe9t\xe9\n".encode("latin-1"))
    facts = extract.build(config.load(tmp_path))
    reason = "source could not be read: UnicodeDecodeError"
    assert facts["components"]["web.latin"]["unknown"] == [
        {"line": 0, "reason": reason, "source": "", "cause": "encoding"}
    ]
    problem = {"line": 0, "reason": reason, "source": "", "cause": "encoding"}
    assert facts["test_file_issues"] == [{"file": "tests/latin.test.ts", "problem": problem}]
    assert facts["components"]["web.service"]["tests_total"] == 1
    assert f"unknown surface: module web.latin (src/latin.ts): {reason}" in (
        source_facts.unknown_fact_lines(facts)
    )


def test_python_files_with_a_byte_order_mark_are_read(tmp_path: Path) -> None:
    """Acceptance: Python accepts a UTF-8 byte order mark, and the extractor does too."""
    write_tree(tmp_path, TINY_PACKAGE)
    source = b'"""Parse requests."""\nfrom pkg.reader import read\n\n\ndef parse(): ...\n'
    (tmp_path / "pkg/parser.py").write_bytes(BOM + source)
    (tmp_path / "tests").mkdir(exist_ok=True)
    test = b"from pkg.parser import parse\n\n\ndef test_parse(): ...\n"
    (tmp_path / "tests/test_parser.py").write_bytes(BOM + test)
    facts = extract.build(config.load(tmp_path))
    record = facts["components"]["pkg.parser"]
    assert "parse_error" not in record
    assert record["docstring"] == "Parse requests."
    assert [entry["name"] for entry in record["names"]] == ["parse"]
    assert record["imports"] == ["pkg.reader"]
    assert record["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert record["tests_total"] == 1
