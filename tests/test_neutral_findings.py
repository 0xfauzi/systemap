"""Finding lines and the model SDK rule of shared logic do not use the syntax of one language.

Before this change:

- The `config_issues` line ended with "the npm tsconfig package could not be read".
- The TypeScript parse error reason in a finding line was "The parser could not parse
  the TypeScript syntax." The Python parse error line names no language.
- `judgement.sdk_of` continued an import name after a dot and after a slash for each
  language. A dot is part of an npm package name, so the TypeScript import `ai.example`
  was an import of the SDK `ai`.

Acceptance:

- The two lines name no language and no package manager.
- An answer item in the earlier form selects the line in the current form, and the
  judgement warnings name the earlier item.
- With the separator of its adapter, a TypeScript fixture that imports `ai.example`
  gives 0 model sdk lines, and an import of `ai/rsc` gives 1. A Python fixture that
  imports `google.adk.tools` gives 1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import write_tree

from systemap import answer_migrations, config, extract, judgement, source_facts
from systemap import language as languages
from systemap.config import Answer
from systemap.model import Component, Model, Region

CONFIG_TREE = {
    "tsconfig.json": '{"extends":"@vendor/tsconfig","compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/index.ts": "export const value = 1;\n",
}
BROKEN_TREE = {
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/broken.ts": "export function broken( {\n",
}


def _lines(tmp_path: Path, tree: dict[str, str]) -> list[str]:
    write_tree(tmp_path, tree)
    return source_facts.unknown_fact_lines(extract.build(config.load(tmp_path)))


def _migrates(line: str, earlier: str) -> None:
    assert answer_migrations.current_line(earlier) == line
    assert answer_migrations.current_line(f"sub: {earlier}") == f"sub: {line}"
    assert answer_migrations.current_line(line) == line
    answer = Answer(items=(earlier,), reason="known", evidence="digest")
    result = judgement.apply_answers([line], [answer], {line: "digest"})
    assert result.open == [] and result.stale == [] and result.pending == []
    assert any(earlier in warning for warning in answer_migrations.warnings([answer]))


def test_the_configuration_package_line_names_no_language(tmp_path: Path) -> None:
    lines = _lines(tmp_path, CONFIG_TREE)
    line = "unknown surface: tsconfig.json extends '@vendor/tsconfig': " + (
        "the configuration package could not be read"
    )
    assert lines == [line]
    earlier = "unknown surface: tsconfig.json extends '@vendor/tsconfig': " + (
        "the npm tsconfig package could not be read"
    )
    _migrates(line, earlier)


def test_the_typescript_parse_line_names_no_language(tmp_path: Path) -> None:
    lines = [line for line in _lines(tmp_path, BROKEN_TREE) if "web.broken" in line]
    assert lines
    assert all("TypeScript" not in line for line in lines)
    line = lines[0]
    assert "The parser could not parse the source syntax." in line
    earlier = line.replace(
        "The parser could not parse the source syntax.",
        "The parser could not parse the TypeScript syntax.",
    )
    _migrates(line, earlier)


def _sdk_lines(tmp_path: Path, tree: dict[str, str], module: str) -> list[str]:
    write_tree(tmp_path, tree)
    cfg = config.load(tmp_path)
    facts: dict[str, Any] = extract.build(cfg)
    adapter = languages.repository(cfg.language)
    model = Model(
        canvas=(400, 200),
        containers=(),
        regions=(Region("all", "ALL", (0, 0, 400, 200)),),
        components=(
            Component("Store", "keeps", implemented_by=(module,), region="all", x=20, y=20),
        ),
        flows=(),
        flow_kinds=(),
    )
    return judgement.model_sdk_imports(
        model, facts, adapter.model_sdks, separators=(adapter.import_separator,)
    )


def test_a_dot_continues_only_a_python_import_name(tmp_path: Path) -> None:
    typescript = {
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
        "tsconfig.json": '{"compilerOptions":{}}',
        "src/plain.ts": 'import { a } from "ai.example";\nexport const b = a;\n',
        "src/model.ts": 'import { c } from "ai/rsc";\nexport const d = c;\n',
    }
    assert _sdk_lines(tmp_path / "ts1", typescript, "web.plain") == []
    assert len(_sdk_lines(tmp_path / "ts2", typescript, "web.model")) == 1
    python = {
        "systemap.toml": 'language = "python"\n',
        "pkg/__init__.py": "",
        "pkg/agent.py": "import google.adk.tools\n",
    }
    found = _sdk_lines(tmp_path / "py", python, "pkg.agent")
    assert found == [
        "model sdk: module pkg.agent imports google.adk and its component Store is not an agent"
    ]
