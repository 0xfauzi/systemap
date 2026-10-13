"""Delta gives a source review line for a component that claims only a symbol.

Codex result change-4. A component with the claim `module:name` has a source review
digest of that module. A source change in the module makes the review stale. Acceptance
value: `delta.compute` gives the line `source review: Tool has changed code in <module>`
for a Python fixture and for a TypeScript fixture. Before the repair, delta gave no line
for Tool, because the module selection excluded symbol claims.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, delta, extract
from systemap.model import Component, Meaning, Model

PYTHON = {
    "systemap.toml": '[package_roots]\n"bot" = "bot"\n',
    "bot/__init__.py": "",
    "bot/agent.py": "def search(term: str) -> str:\n    return term\n",
}
PYTHON_EDIT = ("bot/agent.py", "def search(term: str) -> str:\n    return term + term\n")

TYPESCRIPT = {
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/agent.ts": "export function search(term: string): string { return term }\n",
}
TYPESCRIPT_EDIT = (
    "src/agent.ts",
    "export function search(term: string): string { return term + term }\n",
)


def facts_before_and_after(
    root: Path, tree: dict[str, str], edit: tuple[str, str]
) -> tuple[config.Config, dict[str, Any], dict[str, Any]]:
    write_tree(root, tree)
    cfg = config.load(root)
    before = extract.build(cfg)
    (root / edit[0]).write_text(edit[1], encoding="utf-8")
    return cfg, before, extract.build(cfg)


@pytest.mark.parametrize(
    ("tree", "edit", "module"),
    [(PYTHON, PYTHON_EDIT, "bot.agent"), (TYPESCRIPT, TYPESCRIPT_EDIT, "web.agent")],
    ids=["python", "typescript"],
)
def test_a_symbol_claim_gives_a_source_review_line(
    tmp_path: Path, tree: dict[str, str], edit: tuple[str, str], module: str
) -> None:
    cfg, before, after = facts_before_and_after(tmp_path, tree, edit)
    assert before["components"][module]["syntax_sha"] != after["components"][module]["syntax_sha"]
    model = Model(
        canvas=(0, 0),
        containers=(),
        regions=(),
        components=(
            Component("Agent", "Answers.", implemented_by=(module,)),
            Component("Tool", "Searches.", implemented_by=(f"{module}:search",)),
        ),
        flows=(),
        flow_kinds=(),
    )
    found = delta.compute(cfg, model, Meaning(plain={}), before, after)
    texts = [line.text for line in found.lines if line.kind == "source review"]
    assert f"source review: Tool has changed code in {module}. " in " ".join(texts) + " "
    assert any(text.startswith("source review: Agent ") for text in texts)
