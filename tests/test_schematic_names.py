"""Theme values and model names go into the page and the figures only as safe names or text.

Acceptance (Codex results schematic-1, schematic-2, schematic-6, schematic-7, schematic-8):

- schematic-1: a theme value or a theme table key that contains < > & or " gives
  ValueError. This applies to `[theme]`, `[theme.dark]` and `[theme.light]`, and to the
  keys of the `state`, `container` and `delta` tables, which become CSS names.
- schematic-2: a declared flow kind that contains HTML markup gives no element in the
  SVG. A layer ID that is not a safe name (letters, digits, "_" and "-") gives
  ConfigError when the model loads, because the layer ID becomes a CSS name and an
  SVG marker ID.
- schematic-6: the component IDs `_meta` and `__proto__` give ConfigError when the
  model loads, because the detail data uses `_meta` and the page reads the data as a
  JavaScript object.
- schematic-7: a `[theme.marks]` value that is not ring, notch or dotted gives
  ValueError that names the key and the value.
- schematic-8: each SVG marker ID occurs one time. The arrowhead of a flow in a custom
  layer named `change` or `reach` has the layer color.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest
from conftest import Sample

from systemap import config
from systemap import theme as theme_mod
from systemap.config import ConfigError
from systemap.model import Layer, all_layers
from systemap.schematic import interactive_script
from systemap.schematic import render as render_schematic

CODEX_VALUE = "</style><script>alert(1)</script><style>"
MARKUP_KIND = '"><script>alert(1)</script><path class="'
LAYER_GREEN = "#2CB59A"


def test_the_codex_theme_value_is_refused_in_each_table(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    for tokens in (
        {"ink": CODEX_VALUE},
        {"dark": {"ink": CODEX_VALUE}},
        {"light": {"ink": CODEX_VALUE}},
        {"scheme": "light", "ink": CODEX_VALUE},
    ):
        with pytest.raises(ValueError, match="theme value ink"):
            theme_mod.resolve(tokens, layers)


def test_a_theme_table_key_with_html_marks_is_refused(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    for tokens in (
        {"state": {CODEX_VALUE: ["#1C1A17", "#37332D", "built"]}},
        {"container": {CODEX_VALUE: ["#37332D", "none"]}},
        {"delta": {CODEX_VALUE: "#D4675B"}},
        {"light": {"delta": {"a b": "#D4675B"}}},
    ):
        with pytest.raises(ValueError, match="theme key"):
            theme_mod.resolve(tokens, layers)
    good = theme_mod.resolve({"delta": {"new_tests-2": "#D4675B"}}, layers)
    assert "--d-new_tests-2:#D4675B;" in theme_mod.root_css(good)


def test_a_mark_that_is_not_available_is_refused(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    with pytest.raises(ValueError, match=r"theme value marks\.agent is 'rings'"):
        theme_mod.resolve({"marks": {"agent": "rings"}}, layers)
    with pytest.raises(ValueError, match=r"marks\.tool"):
        theme_mod.resolve({"light": {"marks": {"tool": ""}}}, layers)
    resolved = theme_mod.resolve({"marks": {"agent": "dotted"}}, layers)
    assert resolved["marks"]["agent"] == "dotted"


def test_a_flow_kind_with_markup_gives_no_element(sample: Sample) -> None:
    model = dataclasses.replace(
        sample.model,
        flows=tuple(
            dataclasses.replace(f, kind=MARKUP_KIND) if f.kind == "record" else f
            for f in sample.model.flows
        ),
        flow_kinds=(MARKUP_KIND,),
    )
    meaning = dataclasses.replace(sample.meaning, layer_of_kind={MARKUP_KIND: "record"})
    svg, detail = render_schematic(model, meaning, sample.theme, sample.facts)
    assert "<script" not in svg
    assert 'data-kind="&quot;&gt;&lt;script&gt;' in svg
    assert MARKUP_KIND in json.loads(detail)["_meta"]["kinds"]


MODEL_FILE = """
from systemap import Component, Container, Layer, Meaning, Model, Region

MODEL = Model(
    canvas=(600, 300),
    containers=(Container(id="s", label="S", box=(0, 0, 600, 300)),),
    regions=(Region(id="r", label="R", box=(10, 10, 580, 280), container="s"),),
    components=(Component(CID, "Holds the data.", entry="hold", region="r", x=20, y=40),),
    flows=(),
    flow_kinds=(),
)
MEANING = Meaning(plain={CID: "the data"}, layers=(Layer(LID, "Custom"),))
"""


def load(tmp_path: Path, cid: str = "Store", lid: str = "custom") -> None:
    path = tmp_path / "model.py"
    text = MODEL_FILE.replace("CID", repr(cid)).replace("LID", repr(lid))
    path.write_text(text, encoding="utf-8")
    config.load_model(path, "map/model.py")


def test_a_safe_model_loads(tmp_path: Path) -> None:
    load(tmp_path, "Store", "custom_layer-2")


@pytest.mark.parametrize("lid", ['x"><script>alert(1)</script>', "a b", "a}b", "", "a.b"])
def test_a_layer_id_that_is_not_a_safe_name_is_refused(tmp_path: Path, lid: str) -> None:
    with pytest.raises(ConfigError, match=r"map/model\.py: the layer ID .* is not a safe name"):
        load(tmp_path, lid=lid)


@pytest.mark.parametrize("cid", ["_meta", "__proto__"])
def test_a_component_id_that_the_page_data_uses_is_refused(
    tmp_path: Path, sample: Sample, cid: str
) -> None:
    # The failure on the base: the detail data has one record for `_meta`, and it is
    # the page metadata, so the component record is not in the data.
    if cid == "_meta":
        model = dataclasses.replace(
            sample.model,
            components=tuple(
                dataclasses.replace(c, id="_meta") if c.id == "Writer" else c
                for c in sample.model.components
            ),
            flows=(),
        )
        _svg, detail = render_schematic(model, sample.meaning, sample.theme, sample.facts)
        assert "id" not in json.loads(detail)["_meta"]
    with pytest.raises(ConfigError, match=rf"map/model\.py: the component ID '{cid}'"):
        load(tmp_path, cid=cid)


def change_layer_sample(sample: Sample, name: str) -> tuple[Sample, dict[str, object]]:
    """Give the sample with the custom layer `record` named `name`, in green."""
    layers = tuple(
        Layer(name, "Custom") if lay.id == "record" else lay for lay in sample.meaning.layers
    )
    meaning = dataclasses.replace(sample.meaning, layers=layers, layer_of_kind={"record": name})
    t = theme_mod.resolve({"layers": {name: LAYER_GREEN}}, all_layers(sample.model, meaning))
    return dataclasses.replace(sample, meaning=meaning, theme=t), t


@pytest.mark.parametrize("name", ["change", "reach", "flow"])
def test_a_layer_arrowhead_keeps_the_layer_color(sample: Sample, name: str) -> None:
    s, _t = change_layer_sample(sample, name)
    svg, _ = render_schematic(s.model, s.meaning, s.theme, s.facts)
    ids = re.findall(r'<marker id="([^"]+)"', svg)
    assert len(ids) == len(set(ids)), ids
    heads = dict(re.findall(r'<marker id="([^"]+)"[^>]*><path [^>]*fill="([^"]+)"', svg))
    used = re.findall(rf'data-layer="{name}"[^>]*marker-end="url\(#([^)]+)\)"', svg)
    assert used
    assert all(heads[marker] == LAYER_GREEN for marker in used), (used, heads)


def test_the_inline_detail_data_cannot_change_the_script_end(sample: Sample) -> None:
    """In a script element, "<!--" and then "<script" stop "</script>" from closing the
    element. The inline data must contain no "<!--" and no "</"."""
    text = "<!--<script>x</script>"
    meaning = dataclasses.replace(sample.meaning, plain={**sample.meaning.plain, "Ledger": text})
    _svg, detail = render_schematic(sample.model, meaning, sample.theme, sample.facts)
    script = interactive_script(sample.theme, "schematic", "panel", detail)
    data = script[script.index("var DETAIL = ") + len("var DETAIL = ") : script.index("var PAL")]
    assert "<!--" not in data and "</" not in data
    assert json.loads(data.rstrip().rstrip(";"))["Ledger"]["plain"] == text
