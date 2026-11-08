"""The sequences in the canvas data and the Sequences toolbar of the canvas page
(`canvas_sequences`, `page_canvas_sequences`).

Acceptance values, written before the first run:

1. For each sequence and each step of the self-map (16 sequences and 69 steps), the flow
   index `f` in the canvas data is equal to `flow_ids.step_index` for that step (the rule
   of the linked page, `schematic`). The acts, the measures, the sentence, the label, the
   start, the draft flag and the short entry point name are those of the model and of
   `page_sequences.data`.
2. The canvas data of a tree without sequences has no key `sq` and the same bytes as
   without the sequence part. In a tree with sequences, only a map with sequences has
   the key `sq`.
3. The canvas page has the Sequences toolbar in the header, with the words of the linked
   page (`page_sequences.toolbar`): Sequence, Whole route, Steps, Start at step 1,
   Previous, Next and End sequence. The toolbar is a `role="toolbar"` element with a
   name, the chooser has `aria-haspopup="listbox"` and controls an empty listbox. The CSP
   of the page has the digest of each script element and each style element.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import canvas_sequenced
import pytest
from conftest import write_tree
from test_canvas_page import DATA, _digest, _loaded
from test_nest_join import CONFIG, NESTED, SOURCE, TOP

from systemap import (
    canvas_data,
    canvas_sequences,
    config,
    facts_file,
    flow_ids,
    judgement_json,
    nest,
    page_csp,
    page_sequences,
)
from systemap.cli import main
from systemap.model import Step

REPO = Path(__file__).resolve().parent.parent


def _made(root: Path, files: dict[str, str]) -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    write_tree(root, files)
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    return _loaded(root)


@pytest.fixture(scope="module")
def self_tree() -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    cfg = config.load(REPO)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


def test_the_flow_of_each_step_is_the_flow_of_the_linked_page(self_tree: Any) -> None:
    """Acceptance 1."""
    cfg, tree, facts = self_tree
    data = canvas_data.build(cfg, tree, facts)
    top = tree.top
    shown = data["maps"][0]["sq"]
    journeys = top.meaning.journeys
    assert (len(shown), sum(len(j["s"]) for j in shown)) == (16, 69)
    edge_index = {f.key: i for i, f in enumerate(top.model.flows)}
    linked = page_sequences.data(top.model, top.meaning, facts)["journeys"]
    for one, j, meta in zip(shown, journeys, linked, strict=True):
        assert (one["id"], one["n"], one.get("st", ""), one.get("dr", 0)) == (
            j.id,
            j.label,
            j.starts,
            int(j.drafted),
        )
        assert one.get("en", "") == meta["entry"]
        for step, s in zip(one["s"], j.steps, strict=True):
            assert step["f"] == flow_ids.step_index(s, top.model, edge_index)
            assert (step.get("a", []), step.get("me", []), step.get("y", "")) == (
                list(s.acts),
                list(s.measures),
                s.say,
            )
    assert any(step["f"] >= 0 for one in shown for step in one["s"])


def test_a_step_that_names_no_one_flow_has_the_index_minus_one(tmp_path: Path) -> None:
    """Acceptance 1: the rule of `flow_ids.step_index` for a step with no one flow.

    A model check refuses such a step, so the step is made here and not in a map file."""
    cfg, tree, facts = _made(tmp_path, canvas_sequenced.files())
    nested = tree.get("Gateway")
    model = nested.model
    edge_index = {f.key: i for i, f in enumerate(model.flows)}
    for step in (
        Step(acts=("Views",), measures=("Routes",), say="The views make the page."),
        Step(acts=("Views",), measures=(), edge=("Views", "Auth")),
        *nested.meaning.journeys[0].steps,
    ):
        flow = flow_ids.step_flow(step, model.flows)[0]
        found = flow_ids.step_index(step, model, edge_index)
        assert found == (-1 if flow is None else model.flows.index(flow))
    serve, keep = canvas_data.build(cfg, tree, facts)["maps"][1]["sq"]
    assert [s["f"] for s in serve["s"]] == [0, 1]
    assert keep["dr"] == 1 and "dr" not in serve
    assert flow_ids.step_index(Step(acts=(), measures=()), model, edge_index) == -1


def test_a_tree_without_sequences_has_the_same_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 2."""
    files = {
        "systemap.toml": CONFIG + "[render]\ncanvas = true\n",
        "map/model.py": TOP,
        "map/gateway.py": NESTED,
        **SOURCE,
    }
    cfg, tree, facts = _made(tmp_path, files)
    text = canvas_data.text(canvas_data.build(cfg, tree, facts))
    assert '"sq"' not in text
    monkeypatch.setattr(canvas_sequences, "of_map", lambda m, facts: {})
    assert canvas_data.text(canvas_data.build(cfg, tree, facts)) == text


def test_only_a_map_with_sequences_has_the_key(tmp_path: Path) -> None:
    """Acceptance 2, in a tree with sequences."""
    cfg, tree, facts = _made(tmp_path, canvas_sequenced.files(top=False))
    top, nested = canvas_data.build(cfg, tree, facts)["maps"]
    assert "sq" not in top
    assert [one["id"] for one in nested["sq"]] == ["serve", "keep"]


def test_the_page_has_the_toolbar(tmp_path: Path) -> None:
    """Acceptance 3."""
    cfg, tree, facts = _made(tmp_path, canvas_sequenced.files())
    text = (tmp_path / "docs" / "map" / "index.html").read_text(encoding="utf-8")
    bar = re.search(
        r'<div class="cseq cview" id="cseq".*?End sequence</button></span></div>', text, re.S
    )
    assert bar is not None
    found = bar.group(0)
    for words in (
        "Sequence",
        "Whole route",
        "Steps",
        "Start at step 1",
        "Previous",
        "Next",
        "End sequence",
    ):
        assert f">{words}<" in found
    assert 'role="toolbar" aria-label="Sequence"' in found
    assert 'aria-haspopup="listbox"' in found and 'aria-controls="cseq-list"' in found
    assert re.search(r'id="cseq-list" role="listbox"[^>]*hidden></div>', text)
    head = text.split("<header", 1)[1].split("</header>", 1)[0]
    assert 'id="cseq"' in head
    match = DATA.search(text)
    assert match is not None
    assert json.loads(match.group(1)) == json.loads(
        canvas_data.text(
            canvas_data.build(cfg, tree, facts, judgement_json.open_boundary(tree, facts, cfg))
        )
    )
    directives = dict(part.split(" ", 1) for part in page_csp.of_page(text).split("; "))
    scripts = re.findall(r"<script>(.*?)</script>", text, re.S | re.I)
    styles = re.findall(r"<style>(.*?)</style>", text, re.S | re.I)
    assert sorted(directives["script-src"].split()) == sorted(_digest(s) for s in scripts)
    assert directives["style-src-elem"].split() == [_digest(s) for s in styles]
