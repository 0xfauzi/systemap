"""A figure of one reading: the layer's edges, every card, the legend reduced.

The page switches between readings by hiding edges; a figure of one
reading leaves the other edges out entirely. Both read the same table
(`model.reading`), so the two cannot disagree about which edges a layer
has.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import Sample, init_two_cards, write_tree

from systemap import figure, page
from systemap.cli import main
from systemap.model import all_layers, reading
from systemap.schematic import render as render_schematic

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def drawn_edges(svg: str) -> list[tuple[str, str, str]]:
    """(from, to, layer) of every edge the drawing holds."""
    return re.findall(
        r'class="flow \w+" data-edge="\d+" data-from="([^"]+)" data-to="([^"]+)" '
        r'data-art="[^"]*" data-kind="\w+" data-layer="(\w+)"',
        svg,
    )


def test_a_layer_figure_holds_only_that_layers_edges(sample: Sample) -> None:
    whole, _ = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    assert len(drawn_edges(whole)) == len(sample.model.flows)
    for layer in all_layers(sample.model, sample.meaning):
        svg, detail = render_schematic(
            sample.model, sample.meaning, sample.theme, sample.facts, layer=layer.id
        )
        edges, _subjects = reading(sample.model, sample.meaning, layer.id)
        drawn = drawn_edges(svg)
        assert len(drawn) == len(edges), layer.id
        for src, dst, own in drawn:
            assert (src, dst) in {(f.src, f.dst) for f in sample.model.flows}
            if layer.id not in ("system",):
                assert own == layer.id, f"{layer.id} drew an edge of {own}"
        # Every card stays, whatever the reading shows.
        assert svg.count('class="node ') == len(sample.model.components)
        assert f"<title>{layer.label}: {layer.question}</title>" in svg
        meta = json.loads(detail)
        assert meta["_meta"]["reading"] == layer.id
        for cid, record in meta.items():
            if cid != "_meta":
                assert set(record["edges"]) <= set(edges), cid


def test_structure_has_no_edges_and_system_crosses_the_boundary(sample: Sample) -> None:
    svg, _ = render_schematic(
        sample.model, sample.meaning, sample.theme, sample.facts, layer="structure"
    )
    assert drawn_edges(svg) == []
    assert 'class="flowlbl' not in svg
    svg, _ = render_schematic(
        sample.model, sample.meaning, sample.theme, sample.facts, layer="system"
    )
    assert drawn_edges(svg) == [("User", "Reader", "data")], "the one edge with an actor end"
    hue = sample.theme["layers"]["system"]
    assert f'stroke="{hue}"' in svg, "a derived reading paints its edges in its own hue"
    assert 'marker-end="url(#schematic-m-system)"' in svg
    # An override moves one edge to the model's own layer, and the figure follows.
    svg, _ = render_schematic(
        sample.model, sample.meaning, sample.theme, sample.facts, layer="memory"
    )
    assert drawn_edges(svg) == [("Ledger", "Parser", "memory")]


def test_the_page_reads_the_same_table(sample: Sample) -> None:
    _svg, detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    meta = json.loads(detail)["_meta"]
    for layer in all_layers(sample.model, sample.meaning):
        edges, subjects = reading(sample.model, sample.meaning, layer.id)
        assert meta["readings"][layer.id] == {"edges": edges, "subjects": subjects}
    assert meta["readings"]["structure"] == {
        "edges": [],
        "subjects": [c.id for c in sample.model.components],
    }
    assert meta["readings"]["system"]["subjects"] == ["User"]
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    assert "META.readings" in html, "the page's switch reads the table, not its own rule"


def test_the_legend_and_caption_reduce_to_the_layer(sample: Sample) -> None:
    html, collisions = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, layer="control"
    )
    assert collisions == []
    assert "Control flow</span>" in html
    assert "Data flow</span>" not in html and "Record</span>" not in html
    assert "Control flow: Who drives whom?" in html
    assert "One reading of the system" in html
    html, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, layer="structure"
    )
    assert "Structure: What are the parts, and where does each sit?" in html
    assert "width:1em;height:3px" not in html, "structure draws no line, so no line swatch"
    assert "Control flow</span>" not in html and "Data flow</span>" not in html
    with pytest.raises(figure.ConfigError, match="unknown layer id: nope"):
        figure.make(
            sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, layer="nope"
        )


def test_unknown_layer_exits_2_with_the_fix_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "extract") == 0
    out = tmp_path / "fig.svg"
    assert (
        run("--root", str(tmp_path), "figure", "--static", "--layer", "nope", "--out", str(out))
        == 2
    )
    err = capsys.readouterr().err
    assert "unknown layer id: nope" in err
    assert "structure, system, data, control" in err, "the fix names the readings that exist"
    assert not out.exists()
    assert (
        run("--root", str(tmp_path), "figure", "--static", "--layer", "data", "--out", str(out))
        == 0
    )
    svg = out.read_text()
    assert svg.startswith("<svg ")
    assert "<title>Data flow: What moves, and where does it go?</title>" in svg
    assert drawn_edges(svg) == [("Reader", "Writer", "data")], "the starter model's one flow"


def test_configured_layer_figures_are_refreshed_and_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    toml = tmp_path / "systemap.toml"
    # init configures figures/structure.svg already; a data reading joins it.
    toml.write_text(
        toml.read_text() + '\n[[figures]]\nout = "figures/data.svg"\nmode = "system"\n'
        'interactive = false\nlayer = "data"\n'
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    structure = (tmp_path / "docs/map/figures/structure.svg").read_text()
    data = (tmp_path / "docs/map/figures/data.svg").read_text()
    assert drawn_edges(structure) == []
    assert drawn_edges(data) == [("Reader", "Writer", "data")]
    assert run("--root", str(tmp_path), "check") == 0
    capsys.readouterr()
    (tmp_path / "docs/map/figures/data.svg").write_text(data + "<!-- by hand -->")
    assert run("--root", str(tmp_path), "check") == 1
    assert "docs/map/figures/data.svg differs from what systemap renders" in (
        capsys.readouterr().out
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    # A layer the page does not have is a configuration error, in check and refresh alike.
    toml.write_text(toml.read_text().replace('layer = "data"', 'layer = "nope"'))
    assert run("--root", str(tmp_path), "check") == 2
    assert "unknown layer id: nope" in capsys.readouterr().err
    assert run("--root", str(tmp_path), "refresh") == 2
