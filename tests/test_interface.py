"""The interface rule, and the three fields the panel prints.

A session found sixteen of its twenty-one interface lines wrong after a
check that never read them, and its notes never reached the reader. The
check now reads the leading identifier of every interface line against
the names the component's modules define, and the detail panel prints
the interface, the entry with its module, and the note; a card with a
note carries a dot on the map and in every figure.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import fixture_workspace
import pytest
from conftest import Sample, init_two_cards, write_tree

from systemap import check
from systemap.cli import ALREADY_CURRENT, main
from systemap.model import Component, entry_module
from systemap.schematic import interactive_script, panel_css
from systemap.schematic import render as render_schematic

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def current(root: Path) -> None:
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    assert run("--root", str(root), "refresh") == 0
    assert run("--root", str(root), "check") == 0


def edit_model(root: Path, old: str, new: str) -> None:
    model = root / "map/model.py"
    text = model.read_text()
    assert old in text, old
    model.write_text(text.replace(old, new))


def with_interface(sample: Sample, cid: str, interface: str) -> Sample:
    model = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, interface=interface) if c.id == cid else c
            for c in sample.model.components
        ),
    )
    return dataclasses.replace(sample, model=model)


# ---- the leading identifier ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "head"),
    [
        ("read(source) -> Request", ("read", "")),
        ("Ledger.record / Ledger.history", ("Ledger", "record")),
        ("  run_single_shot(...) -> structured output", ("run_single_shot", "")),
        ("app (the framework's App) with two plugins", ("app", "")),
        ("PageModel / ResolvedPageModel", ("PageModel", "")),
        ("SandboxRunner.run(code, inputs) -> tree | TypedSandboxError", ("SandboxRunner", "run")),
        ("build -> facts", ("build", "")),
        ("MODEL: Model and MEANING: Meaning", ("MODEL", "")),
        ("systemap <command> [--root DIR]", ("systemap", "")),
        ("GET /sessions", ("GET", "")),
        ("--base REF", None),
        ("[[figures]] out = ...", None),
        ("", None),
    ],
)
def test_interface_head_is_the_token_before_a_paren_dot_arrow_or_space(
    text: str, head: tuple[str, str] | None
) -> None:
    assert check.interface_head(text) == head


def test_interface_leading_name_must_be_defined_by_the_modules(sample: Sample) -> None:
    assert check.check_interface(sample.model, sample.facts) == []
    # A misspelt function, refused with the closest defined name.
    lines = check.check_interface(
        with_interface(sample, "Reader", "raed(source)").model, sample.facts
    )
    assert lines == [
        "Reader interface starts with raed, which none of its modules defines "
        "(pkg.reader); closest: read"
    ]
    # Class.method: the class is defined, the method must be one of its public methods.
    lines = check.check_interface(
        with_interface(sample, "Ledger", "Ledger.recrod(parts)").model, sample.facts
    )
    assert lines == [
        "Ledger interface names Ledger.recrod, but Ledger has no public method recrod "
        "(pkg.ledger); closest: record"
    ]
    assert (
        check.check_interface(
            with_interface(sample, "Ledger", "Ledger.history()").model, sample.facts
        )
        == []
    )
    # A command, a route, a flag: none is a name the modules define.
    lines = check.check_interface(
        with_interface(sample, "Parser", "python -m pkg").model, sample.facts
    )
    assert lines == [
        "Parser interface starts with python, which none of its modules defines "
        "(pkg.parser); closest: parse"
    ]
    lines = check.check_interface(with_interface(sample, "Parser", "--verbose").model, sample.facts)
    assert lines == [
        "Parser interface '--verbose' does not start with a name; start it with a public "
        "name one of its modules defines (pkg.parser)"
    ]
    # Optional: an empty line is not checked, and an actor claims no code.
    assert check.check_interface(with_interface(sample, "Parser", "").model, sample.facts) == []
    assert (
        check.check_interface(with_interface(sample, "User", "types()").model, sample.facts) == []
    )
    # No facts, nothing to check against; the coverage rule reports that.
    assert check.check_interface(sample.model, {}) == []


def test_a_symbol_claim_counts_as_a_defined_name() -> None:
    facts: dict[str, Any] = {
        "components": {
            "bot.agent": {
                "names": [{"name": "search", "kind": "function"}],
                "classes": [{"name": "Tool", "methods": ["def call(self, q: str) -> str"]}],
            }
        }
    }
    tool = Component("Search", "looks up", implemented_by=("bot.agent:search",), entry="search")
    model = dataclasses.replace(
        fixture_workspace.MODEL, components=(tool,), flows=(), invariants=()
    )
    ok = dataclasses.replace(
        model, components=(dataclasses.replace(tool, interface="search(term)"),)
    )
    assert check.check_interface(ok, facts) == []
    by_class = dataclasses.replace(
        model,
        components=(
            dataclasses.replace(
                tool, implemented_by=("bot.agent:Tool",), entry="Tool", interface="Tool.call(q)"
            ),
        ),
    )
    assert check.check_interface(by_class, facts) == []
    bad = dataclasses.replace(
        model, components=(dataclasses.replace(tool, interface="lookup(term)"),)
    )
    assert check.check_interface(bad, facts) == [
        "Search interface starts with lookup, which none of its modules defines "
        "(bot.agent:search); closest: search"
    ]


def test_interface_failure_in_the_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current(tmp_path)
    capsys.readouterr()
    edit_model(tmp_path, 'interface="write(request) -> Result",', 'interface="publish(request)",')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "interface: 1 problem" in out
    assert (
        "Writer interface starts with publish, which none of its modules defines "
        "(pkg.writer); closest: write"
    ) in out
    assert "fix: in map/model.py, start interface with a public name" in out
    assert out.rstrip().endswith("fix map/model.py, then run: systemap check")
    assert run("--root", str(tmp_path), "refresh") == 1


# ---- the anonymised fixture: twenty-four real interface lines --------------------------

# The leading name each fixture interface line resolves to, by hand, so the
# tokenizer is measured against lines a real map wrote.
FIXTURE_HEADS: dict[str, tuple[str, str]] = {
    "Gateway": ("create_app", ""),
    "GatewayStore": ("GatewayStore", ""),
    "ArtifactStore": ("DiskArtifactService", ""),
    "PageModel": ("PageModel", ""),
    "StyleGuide": ("StyleGuide", ""),
    "WireContracts": ("GenerateRequest", ""),
    "SourceExtractor": ("ingest", ""),
    "FolioPlanner": ("plan", ""),
    "Orchestrator": ("app", ""),
    "RosterClient": ("run_single_shot", ""),
    "PromptTemplates": ("render_prompt", ""),
    "BudgetLedger": ("BudgetLedgerPlugin", ""),
    "Config": ("build_roster", ""),
    "GuideCache": ("GuideCache", ""),
    "StyleCompiler": ("extract", ""),
    "StyleCompleter": ("complete", ""),
    "ComponentGallery": ("build_gallery", ""),
    "CropPicker": ("pick_crops", ""),
    "TextMeasurer": ("measure_text", ""),
    "LayoutEngine": ("solve", ""),
    "Sandbox": ("SandboxRunner", "run"),
    "ComponentLibrary": ("ComponentLibrary", "search"),
    "SourceLineage": ("build_source_line", ""),
    "OfxEmitter": ("emit_folio", ""),
    "Renderer": ("RenderService", "png"),
}


def first_module(component: Component) -> str:
    """The first concrete module a component claims: a `.*` claim resolved, a
    symbol claim's module."""
    pattern = component.implemented_by[0].partition(":")[0]
    if pattern.endswith(".*"):
        head = pattern[:-2]
        return next(m for m in fixture_workspace.MODULES if m == head or m.startswith(head + "."))
    return pattern


def fixture_facts_with_heads() -> dict[str, Any]:
    """The fixture's facts with each interface's leading name defined by its first module."""
    facts = fixture_workspace.facts()
    for c in fixture_workspace.MODEL.components:
        if c.kind == "actor":
            continue
        name, method = FIXTURE_HEADS[c.id]
        record = facts["components"][first_module(c)]
        record.setdefault("names", []).append(
            {"name": name, "kind": "class" if method else "function"}
        )
        if method:
            record["classes"].append({"name": name, "methods": [f"def {method}(self) -> None"]})
    return facts


def test_fixture_interfaces_pass_and_a_wrong_head_is_refused() -> None:
    model = fixture_workspace.MODEL
    heads = {c.id: check.interface_head(c.interface) for c in model.components if c.kind != "actor"}
    assert heads == FIXTURE_HEADS
    facts = fixture_facts_with_heads()
    assert check.check_interface(model, facts) == []
    # One misspelt function and one wrong method, each refused with the closest name.
    broken = dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(c, interface="create_ap() -> FastAPI")
            if c.id == "Gateway"
            else dataclasses.replace(c, interface="SandboxRunner.go(code)")
            if c.id == "Sandbox"
            else c
            for c in model.components
        ),
    )
    lines = check.check_interface(broken, facts)
    assert lines == [
        "Gateway interface starts with create_ap, which none of its modules defines "
        "(wharf_server.gateway, wharf_server.gateway.__main__, wharf_server.gateway.app, "
        "wharf_server.gateway.errors, wharf_server.gateway.extraction_run, "
        "wharf_server.gateway.jobs, wharf_server.gateway.routes, "
        "wharf_server.gateway.stub_run); closest: create_app",
        "Sandbox interface names SandboxRunner.go, but SandboxRunner has no public method go "
        "(wharf_server.sandbox, wharf_server.sandbox.container, wharf_server.sandbox.errors, "
        "wharf_server.sandbox.runner, wharf_server.sandbox.tuning); closest: run",
    ]


# ---- the panel: interface, entry with its module, note; the dot on the card ------------


def test_panel_carries_interface_entry_and_note(sample: Sample) -> None:
    noted = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, note="the ledger is rebuilt on every start")
            if c.id == "Ledger"
            else c
            for c in sample.model.components
        ),
    )
    svg, detail = render_schematic(noted, sample.meaning, sample.theme, sample.facts)
    data = json.loads(detail)
    assert data["Reader"]["interface"] == "read(source) -> Request"
    assert data["Reader"]["entry"] == "read" and data["Reader"]["entry_module"] == "pkg.reader"
    assert data["Ledger"]["entry_module"] == "pkg.ledger"
    assert data["Ledger"]["note"] == "the ledger is rebuilt on every start"
    assert data["Reader"]["note"] == "" and data["User"]["entry_module"] == ""
    # The dot: on the noted card only, with the note as its hover text.
    assert svg.count('class="node__note"') == 1
    assert "<title>the ledger is rebuilt on every start</title>" in svg
    # The figure is the same drawing, so it carries the dot too.
    svg_layer, _ = render_schematic(
        noted, sample.meaning, sample.theme, sample.facts, layer="structure"
    )
    assert svg_layer.count('class="node__note"') == 1
    # The panel prints the three fields; a store with no entry is a namespace.
    script = interactive_script(sample.theme, "schematic", "panel", detail)
    for text in (
        "systemap-f__iface",
        "systemap-f__note",
        "entry: <b>",
        "none (a namespace)",
        "d.entry_module",
    ):
        assert text in script, text
    css = panel_css(sample.theme)
    for cls in (".systemap-f__iface", ".systemap-f__note", ".systemap-f__entry"):
        assert cls in css, cls
    # entry_module resolves a symbol claim to the module that holds the symbol.
    tool = Component("T", "t", implemented_by=("pkg.ledger:Ledger",), entry="Ledger")
    assert entry_module(tool, sample.facts) == "pkg.ledger"
    assert entry_module(dataclasses.replace(tool, entry="Nope"), sample.facts) == ""


def test_an_interface_edit_renders_and_refresh_says_what_current_means(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    edit_model(
        tmp_path, 'interface="write(request) -> Result",', 'interface="write(request) -> str",'
    )
    # The interface is a rendered field now: the page is stale after the edit.
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "docs/map/index.html differs from what systemap renders" in out
    assert run("--root", str(tmp_path), "refresh") == 0
    assert "map: updated" in capsys.readouterr().out
    assert "write(request) -> str" in (tmp_path / "docs/map/index.html").read_text()
    assert run("--root", str(tmp_path), "refresh") == 0
    assert capsys.readouterr().out == ALREADY_CURRENT + "\n"
    assert ALREADY_CURRENT == (
        "map: already current: the page matches the model's rendered fields and the facts"
    )
