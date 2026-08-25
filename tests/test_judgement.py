"""`systemap judgement`: one line per thing a maintainer should look at."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from conftest import Sample, sample_model, write_tree

from systemap import judgement
from systemap.cli import main
from systemap.config import Ignore
from systemap.model import Flow, Layer, Meaning


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
    assert judgement.mis_folds(sample.model, sample.facts) == []
    odd = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, id="Keeper") if c.id == "Ledger" else c
            for c in sample.model.components
        ),
    )
    lines = judgement.mis_folds(odd, sample.facts)
    assert lines == ["possible mis-fold: Keeper claims pkg.ledger (no shared word)"]


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
