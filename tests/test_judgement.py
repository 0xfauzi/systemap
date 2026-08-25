"""`systemap judgement`: one line per thing a maintainer should look at."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import fixture_workspace
import pytest
from conftest import Sample, sample_model, write_tree

from systemap import config, judgement
from systemap.cli import main
from systemap.config import Answer, Ignore
from systemap.model import Component, Flow, Journey, Layer, Meaning, Model, Region, Step


def test_words_and_shared_words() -> None:
    assert judgement.words("FactsExtractor") == {"facts", "extractor"}
    assert judgement.words("change_map") == {"change", "map"}
    assert judgement.words("CLI") == {"cli"}
    assert judgement.shares_a_word("FactsExtractor", "extract")
    assert judgement.shares_a_word("Router", "route")
    assert judgement.shares_a_word("CLI", "cli")
    assert not judgement.shares_a_word("Ledger", "store")
    # Three letters are not a stem: "map" must not match "mapping" by prefix.
    assert not judgement.shares_a_word("Map", "mapping")


def test_single_module_lines(sample: Sample) -> None:
    lines = judgement.single_module(sample.model, sample.facts)
    assert "single module: Reader is only pkg.reader" in lines
    assert "single module: Ledger is only pkg.ledger" in lines
    # The actor claims nothing and is never listed.
    assert not any("User" in line for line in lines)


def test_single_module_reads_implemented_by_without_facts() -> None:
    model, _ = sample_model()
    lines = judgement.single_module(model, {})
    assert "single module: Ledger is only pkg.ledger" in lines


def test_mis_fold_lines(sample: Sample) -> None:
    assert judgement.mis_folds(sample.model, sample.meaning, sample.facts) == []
    # A component of one module is the single-module line's business, never a mis-fold.
    odd = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, id="Keeper") if c.id == "Ledger" else c
            for c in sample.model.components
        ),
    )
    plain = {**sample.meaning.plain, "Keeper": "the record book"}
    meaning = dataclasses.replace(sample.meaning, plain=plain)
    assert judgement.mis_folds(odd, meaning, sample.facts) == []


def _claims(*modules: str, does: str = "Keeps every record ever written.") -> Model:
    return Model(
        canvas=(600, 200),
        containers=(),
        regions=(Region("all", "ALL", (0, 0, 600, 200)),),
        components=(
            Component(
                "Keeper",
                does,
                interface="Ledger.record / Ledger.history",
                implemented_by=modules,
                entry="Ledger",
                region="all",
                x=20,
                y=20,
            ),
        ),
        flows=(),
        flow_kinds=(),
    )


def _facts(*modules: str) -> dict[str, Any]:
    return {"components": {m: {"functions": [], "classes": [], "uses": {}} for m in modules}}


def test_mis_fold_fires_only_on_a_stranger_in_a_foreign_package() -> None:
    meaning = Meaning(plain={"Keeper": "the record book"})
    modules = ("pkg.ledger", "pkg.util.retry")
    # pkg.util.retry: no word in common with Keeper, its does, its plain word or its
    # interface, and pkg.util holds no other module of Keeper's.
    assert judgement.mis_folds(_claims(*modules), meaning, _facts(*modules)) == [
        "possible mis-fold: Keeper claims pkg.util.retry (no word shared with the "
        "component, and no other module of it in pkg.util)"
    ]
    # A word in the full path clears it: the package segment counts.
    modules = ("pkg.ledger", "pkg.ledgers.retry")
    assert judgement.mis_folds(_claims(*modules), meaning, _facts(*modules)) == []
    # A word in does clears it.
    modules = ("pkg.ledger", "pkg.util.retry")
    model = _claims(*modules, does="Keeps every record; a retry covers a failed write.")
    assert judgement.mis_folds(model, meaning, _facts(*modules)) == []
    # A word in plain clears it.
    plain = Meaning(plain={"Keeper": "the book with a retry"})
    assert judgement.mis_folds(_claims(*modules), plain, _facts(*modules)) == []
    # A neighbour in the same package clears it: two strangers side by side are a
    # differently named pair of files, not a fold.
    modules = ("pkg.ledger", "pkg.util.retry", "pkg.util.backoff")
    assert judgement.mis_folds(_claims(*modules), meaning, _facts(*modules)) == []
    # A subpackage's own root, claimed beside its children, sits with them.
    modules = ("pkg.util", "pkg.util.retry")
    assert judgement.mis_folds(_claims(*modules), meaning, _facts(*modules)) == []
    assert judgement.package_of("pkg") == "pkg"
    assert judgement.package_of("pkg.util.retry") == "pkg.util"
    assert judgement.share_a_package("pkg.util", "pkg.util.retry")
    assert judgement.share_a_package("pkg.a", "pkg.b")
    assert not judgement.share_a_package("pkg.a.x", "pkg.b.y")


def test_mis_fold_count_on_the_workspace_fixture() -> None:
    """The anonymised map a fresh run produced: 112 lines under the last-segment rule."""
    facts = fixture_workspace.facts()
    assert len(facts["components"]) == 144
    assert len(fixture_workspace.MODEL.components) == 27
    lines = judgement.mis_folds(fixture_workspace.MODEL, fixture_workspace.MEANING, facts)
    assert lines == []
    # The rule still fires here when a module is a stranger to its component:
    # move one style module into the config card and the line names it.
    moved = dataclasses.replace(
        fixture_workspace.MODEL,
        components=tuple(
            dataclasses.replace(c, implemented_by=(*c.implemented_by, "wharf_server.style.walker"))
            if c.id == "Config"
            else c
            for c in fixture_workspace.MODEL.components
        ),
    )
    assert judgement.mis_folds(moved, fixture_workspace.MEANING, facts) == [
        "possible mis-fold: Config claims wharf_server.style.walker (no word shared with the "
        "component, and no other module of it in wharf_server.style)"
    ]


def test_no_sentence_lines(sample: Sample) -> None:
    assert judgement.no_sentence(sample.model, sample.meaning) == []
    relations = dict(sample.meaning.relations)
    relations[("Reader", "Parser")] = "   "
    del relations[("Writer", "Ledger")]
    gappy = dataclasses.replace(sample.meaning, relations=relations)
    lines = judgement.no_sentence(sample.model, gappy)
    assert lines == [
        "no sentence: Reader -> Parser ('parse')",
        "no sentence: Writer -> Ledger ('record')",
    ]


def test_thin_layer_lines(sample: Sample) -> None:
    # The sample's memory layer carries one edge, so it lights two components;
    # its one control flow lights two as well.
    assert judgement.thin_layers(sample.model, sample.meaning) == []
    thin = dataclasses.replace(
        sample.meaning,
        layers=(*sample.meaning.layers, Layer("audit", "Audit")),
        layer_overrides={},
    )
    lines = judgement.thin_layers(sample.model, thin)
    assert lines == [
        "thin layer: memory lights 0 components",
        "thin layer: audit lights 0 components",
    ]
    # A standard kind the model never uses is a thin standard layer: the
    # line asks whether it was missed. The derived readings are never thin.
    no_control = dataclasses.replace(
        sample.model,
        flows=tuple(f for f in sample.model.flows if f.kind != "control"),
    )
    lines = judgement.thin_layers(no_control, sample.meaning)
    assert lines == ["thin layer: control lights 0 components"]
    assert not any("structure" in line or "system" in line for line in lines)
    one = dataclasses.replace(
        sample.model,
        flows=(Flow("Ledger", "Ledger", "self", "record"),),
    )
    only_self = Meaning(
        plain=sample.meaning.plain,
        layers=(Layer("self", "Self"),),
        layer_of_kind={"record": "self"},
        relations={},
        layer_overrides={("Ledger", "Ledger"): "self"},
    )
    lines = judgement.thin_layers(one, only_self)
    assert "thin layer: self lights 1 component" in lines
    lonely = dataclasses.replace(only_self, layers=(Layer("self", "Self"), Layer("x", "X")))
    assert "thin layer: x lights 0 components" in judgement.thin_layers(one, lonely)


def test_ignored_lines(sample: Sample) -> None:
    lines = judgement.ignored(
        sample.facts,
        (Ignore("pkg", "the package root"), Ignore("pkg.gone", "it left")),
    )
    assert lines == ["ignored: pkg (the package root)", "ignored: pkg.gone (it left)"]


def test_report_wording() -> None:
    assert judgement.report([]) == ["judgement: nothing to confirm"]
    assert judgement.report(["a"]) == ["judgement: 1 item for the maintainer to confirm", "  a"]


def test_answers_suppress_count_and_go_stale() -> None:
    lines = ["single module: A is only p.a", "thin layer: control lights 0 components", "x"]
    answers = (
        Answer(("single module: A is only p.a",), "a real part; the module is the part"),
        Answer(("thin layer: control lights 0 components", "gone: y"), "no control flow yet"),
    )
    result = judgement.apply_answers(lines, answers)
    assert result.open == ["x"]
    assert result.answered == 2
    assert result.stale == ["gone: y"]
    assert judgement.report(result) == [
        "judgement: 1 item for the maintainer to confirm, 2 answered, 1 stale",
        "  x",
        "  stale answer: 'gone: y' no longer appears; remove it from [judgement] answered",
    ]
    everything = judgement.apply_answers(lines[:2], answers[:2])
    assert judgement.report(everything)[0] == "judgement: nothing to confirm, 2 answered, 1 stale"
    assert judgement.apply_answers([], ()) == judgement.Answered([], 0, [])


def test_answers_in_the_configuration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
        },
    )
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text()
        + """
[judgement]
answered = [
    { items = ["single module: Reader is only pkg.reader", "single module: Writer is only pkg.writer"], reason = "two real parts of a two-file package" },
    { item = "thin layer: control lights 0 components", reason = "nothing drives anything yet" },
    { item = "single module: Gone is only pkg.gone", reason = "answered before the card was removed" },
]
"""
    )
    assert main(["--root", str(tmp_path), "judgement"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("judgement: 1 item for the maintainer to confirm, 3 answered, 1 stale")
    assert "single module: Reader" not in out.replace("stale answer", "")
    assert "ignored: pkg (" in out
    assert (
        "stale answer: 'single module: Gone is only pkg.gone' no longer appears; "
        "remove it from [judgement] answered"
    ) in out
    # An answer without a reason, with both forms, or with neither, is a configuration error.
    for bad, message in (
        ('{ item = "x" }', "needs a reason"),
        ('{ item = "x", items = ["y"], reason = "r" }', "not both and not neither"),
        ('{ reason = "r" }', "not both and not neither"),
        ('{ items = [], reason = "r" }', "non-empty list of lines"),
        ('{ item = "x", reason = "r", why = "w" }', "unknown key: why"),
    ):
        toml.write_text(f"[judgement]\nanswered = [{bad}]\n")
        assert main(["--root", str(tmp_path), "judgement"]) == 2
        assert message in capsys.readouterr().err
    toml.write_text("[judgement]\nreplied = []\n")
    assert main(["--root", str(tmp_path), "judgement"]) == 2
    assert "judgement has unknown key: replied" in capsys.readouterr().err
    toml.write_text('[judgement]\nanswered = [{ item = "  x  ", reason = "r" }]\n')
    cfg = config.load(tmp_path)
    assert cfg.judgement_answered == (Answer(("x",), "r"),)


def test_judgement_command_always_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
        },
    )
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    capsys.readouterr()
    # Before extract: the model alone, and still exit 0.
    assert main(["--root", str(tmp_path), "judgement"]) == 0
    out = capsys.readouterr().out
    assert "no facts at docs/map/map.json" in out
    assert "single module: Reader is only pkg.reader" in out
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "judgement"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("judgement: 4 items for the maintainer to confirm")
    assert "single module: Reader is only pkg.reader" in out
    assert "single module: Writer is only pkg.writer" in out
    # The starter has one data flow and no control flow: the standard layer is thin.
    assert "thin layer: control lights 0 components" in out
    assert "ignored: pkg (the package root only marks the directory as a package)" in out
    # A model that contradicts itself is a configuration error, exit 2.
    (tmp_path / "map/model.py").write_text("MODEL = 1\n")
    assert main(["--root", str(tmp_path), "judgement"]) == 2


# ---- the second pass: entry points and crossing imports ------------------------


def entry_facts() -> dict[str, Any]:
    """Facts for a package with a CLI of three subcommands, a worker and a root function."""
    return {
        "components": {
            "pkg": {"functions": [{"name": "open_thing"}], "classes": [], "uses": {}},
            "pkg.__main__": {"functions": [], "classes": [], "uses": {"pkg.cli": ["*"]}},
            "pkg.cli": {
                "functions": [{"name": "main"}],
                "classes": [],
                "uses": {"pkg.reader": ["read"], "pkg.ledger": ["Ledger"]},
            },
            "pkg.reader": {"functions": [{"name": "read"}], "classes": [], "uses": {}},
            "pkg.ledger": {"functions": [], "classes": [{"name": "Ledger"}], "uses": {}},
            "pkg.worker": {"functions": [{"name": "main"}], "classes": [], "uses": {}},
        },
        "entry_points": [
            {"kind": "console_script", "name": "pkg", "module": "pkg.cli", "target": "main"},
            {"kind": "public_function", "name": "open_thing", "module": "pkg", "target": ""},
            {
                "kind": "main_module",
                "name": "python -m pkg",
                "module": "pkg.__main__",
                "target": "",
            },
            {"kind": "main_function", "name": "main", "module": "pkg.cli", "target": "main"},
            {"kind": "subcommand", "name": "init", "module": "pkg.cli", "target": "pkg"},
            {"kind": "subcommand", "name": "check", "module": "pkg.cli", "target": "pkg"},
            {"kind": "subcommand", "name": "render", "module": "pkg.cli", "target": "pkg"},
            {"kind": "main_function", "name": "main", "module": "pkg.worker", "target": "main"},
        ],
    }


def entry_model() -> tuple[Model, Meaning]:
    model = Model(
        canvas=(900, 300),
        containers=(),
        regions=(Region("all", "ALL", (16, 16, 868, 268)),),
        components=(
            Component(
                "CLI",
                "the commands",
                implemented_by=("pkg.cli", "pkg.__main__"),
                entry="main",
                region="all",
                x=40,
                y=100,
            ),
            Component(
                "Reader",
                "reads",
                implemented_by=("pkg.reader", "pkg"),
                entry="read",
                region="all",
                x=300,
                y=100,
            ),
            Component(
                "Ledger",
                "keeps",
                implemented_by=("pkg.ledger",),
                entry="Ledger",
                kind="store",
                region="all",
                x=560,
                y=100,
            ),
            Component(
                "Worker",
                "works",
                implemented_by=("pkg.worker",),
                entry="main",
                region="all",
                x=560,
                y=200,
            ),
        ),
        flows=(Flow("CLI", "Reader", "source", "control"),),
        flow_kinds=(),
    )
    meaning = Meaning(
        plain={
            "CLI": "the commands",
            "Reader": "the reader",
            "Ledger": "the ledger",
            "Worker": "the worker",
        },
        relations={("CLI", "Reader"): "init and check read the source."},
        journeys=(
            Journey(
                "first-run",
                "The first run: pkg init, then a verification",
                steps=(
                    Step(
                        ("CLI",),
                        (),
                        ("CLI", "Reader"),
                        "The person runs the checker; INIT wrote the config.",
                    ),
                ),
            ),
        ),
    )
    return model, meaning


def test_entry_points_without_journey() -> None:
    model, meaning = entry_model()
    lines = judgement.entry_points_without_journey(model, meaning, entry_facts())
    # "pkg" and "init" are mentioned (the label; the step, case blind); "check"
    # is not, "checker" is a different word. main() in pkg.cli is the console
    # script's twin and python -m pkg imports it; both are asked once, as pkg.
    # The worker's main and the root's public function have no journey.
    assert lines == [
        "entry point open_thing() in pkg has no journey (component Reader)",
        "entry point pkg check (subcommand) has no journey (component CLI)",
        "entry point pkg render (subcommand) has no journey (component CLI)",
        "entry point main() in pkg.worker has no journey (component Worker)",
    ]
    # A journey that names them clears the lines.
    covered = dataclasses.replace(
        meaning,
        journeys=(
            *meaning.journeys,
            Journey("more", "check, render, open_thing and the worker's main", ()),
        ),
    )
    assert judgement.entry_points_without_journey(model, covered, entry_facts()) == []
    assert judgement.entry_points_without_journey(model, meaning, {}) == []


def test_mentioned_is_a_whole_word() -> None:
    assert judgement.mentioned("check", "the person runs pkg check first")
    assert judgement.mentioned("check", "Check the map.")
    assert not judgement.mentioned("check", "the checker runs")
    assert not judgement.mentioned("init", "the initial draft")
    assert not judgement.mentioned("pkg", "pkg-worker starts")
    assert judgement.mentioned("python -m pkg", "run python -m pkg to start")


def test_crossing_imports_without_flow() -> None:
    model, _ = entry_model()
    lines = judgement.crossing_imports_without_flow(model, entry_facts())
    # pkg.cli imports pkg.reader (a flow joins CLI and Reader: silent) and
    # pkg.ledger (no flow joins CLI and Ledger: asked). pkg.__main__ imports
    # pkg.cli inside the same component: silent.
    assert lines == [
        "crossing import: module pkg.cli (component CLI) imports module pkg.ledger "
        "(component Ledger) and no flow joins CLI and Ledger"
    ]
    # A flow in the other direction is enough: the rule is about the pair.
    joined = dataclasses.replace(model, flows=(*model.flows, Flow("Ledger", "CLI", "rows", "data")))
    assert judgement.crossing_imports_without_flow(joined, entry_facts()) == []
    assert judgement.crossing_imports_without_flow(model, {}) == []


def test_model_sdk_lines() -> None:
    facts = entry_facts()
    facts["components"]["pkg.reader"]["external"] = ["anthropic.types", "yaml"]
    facts["components"]["pkg.ledger"]["external"] = ["google.adk", "google.adk.tools"]
    facts["components"]["pkg.worker"]["external"] = ["openai"]
    facts["components"]["pkg.cli"]["external"] = ["boto3", "housemodel.client"]
    model, _ = entry_model()
    model = dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(c, kind="agent") if c.id == "Worker" else c
            for c in model.components
        ),
    )
    # The worker is an agent: silent. The reader and the ledger are not: one line
    # per SDK, the dotted namespace collapsed to the SDK it belongs to. boto3 is
    # not on the list; a house SDK joins it through the configuration.
    assert judgement.model_sdk_imports(model, facts) == [
        "model sdk: module pkg.ledger imports google.adk and its component Ledger is not an agent",
        "model sdk: module pkg.reader imports anthropic and its component Reader is not an agent",
    ]
    extended = (*judgement.MODEL_SDKS, "housemodel")
    assert judgement.model_sdk_imports(model, facts, extended)[0] == (
        "model sdk: module pkg.cli imports housemodel and its component CLI is not an agent"
    )
    assert judgement.sdk_of("google.adk.tools", judgement.MODEL_SDKS) == "google.adk"
    assert judgement.sdk_of("googles", judgement.MODEL_SDKS) == ""
    assert "boto3" not in judgement.MODEL_SDKS
    assert judgement.model_sdk_imports(model, {}) == []


def test_model_sdks_configured(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "import housemodel\n\n\ndef read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
            "systemap.toml": '[facts]\nmodel_sdks = ["housemodel"]\n',
        },
    )
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "judgement"]) == 0
    out = capsys.readouterr().out
    assert (
        "model sdk: module pkg.reader imports housemodel and its component Reader is not an agent"
        in out
    )
    (tmp_path / "systemap.toml").write_text("[facts]\nsdks = []\n")
    assert main(["--root", str(tmp_path), "judgement"]) == 2
    assert "facts has unknown key: sdks" in capsys.readouterr().err


def test_run_orders_the_second_pass_before_ignores(sample: Sample) -> None:
    model, meaning = entry_model()
    facts = entry_facts()
    facts["components"]["pkg.reader"]["external"] = ["openai"]
    lines = judgement.run(model, meaning, facts, (Ignore("pkg.gone", "left"),))
    order = [
        k
        for k in ("thin layer", "entry point", "crossing import", "model sdk", "ignored")
        if any(line.startswith(k) for line in lines)
    ]
    assert order == ["thin layer", "entry point", "crossing import", "model sdk", "ignored"]
