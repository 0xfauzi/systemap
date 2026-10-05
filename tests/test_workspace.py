"""The operational map preserves source evidence and exact review identifiers.

Acceptance: no substituted findings, no missing authored steps, and the sample
stays within the existing self-contained 300 KiB page limit (test_render.py).
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample

from systemap import config, judgement, page, page_data, theme
from systemap.config import Answer
from systemap.model import all_layers
from systemap.schematic import render


def payload(html: str) -> dict[str, Any]:
    found = re.search(r"<script>window.systemapWorkspace=(.*);</script>", html)
    assert found
    return json.loads(found[1])  # type: ignore[no-any-return]


def test_review_keeps_identifiers_and_leaves_unverified_answers_pending(sample: Sample) -> None:
    lines = judgement.run(sample.model, sample.meaning, sample.facts)
    answer = Answer(items=(lines[0],), reason="This part has a separate responsibility.")
    cfg = dataclasses.replace(sample.cfg, judgement_answered=(answer,))
    data = page_data.review(cfg, sample.model, sample.meaning, sample.facts)
    assert [r["line"] for r in data["open"]] == lines
    assert data["answered"] == []
    assert data["pending"] and "unavailable" in data["pending"][0]
    assert data["open"][0]["parts"], "a single-module finding identifies its part"


def test_script_cannot_be_closed_by_authored_prose(sample: Sample) -> None:
    malicious = "</script><script>window.intruder=true</script>"
    facts = json.loads(json.dumps(sample.facts))
    facts["components"]["pkg.reader"]["docstring"] = malicious
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, facts, {})
    assert malicious not in html
    assert payload(html)["sources"]["Reader"]["modules"][0]["docstring"] == malicious


def test_source_records_resolve_wildcard_claims(sample: Sample) -> None:
    model = dataclasses.replace(
        sample.model,
        components=(dataclasses.replace(sample.model.components[1], implemented_by=("pkg.*",)),),
    )
    sources = page_data.sources(model, sample.facts)
    record = next(iter(sources.values()))
    assert {m["id"] for m in record["modules"]} == set(sample.facts["components"])
    assert "pkg.*" in record["claims"]


@pytest.mark.skipif(shutil.which("node") is None, reason="workspace interactions need Node")
def test_operations_search_and_review_share_the_same_map(sample: Sample, tmp_path: Path) -> None:
    out = tmp_path / "map.html"
    out.write_text(
        page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js")
    result = subprocess.run(
        [shutil.which("node") or "node", str(driver), str(out), "--scenario", "workspace"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["initialMode"] == "understand"
    assert report["operations"] == len(sample.meaning.journeys)
    assert report["steps"] == report["expectedSteps"]
    assert report["activeStart"] == report["activeClicked"] == "1"
    assert report["activeNext"] == "2"
    assert "Rules for this step" in report["evidence"]
    assert report["partMode"] == "trace" and report["partFocus"]
    assert report["partPurpose"]
    assert report["matches"] == ["Reader"] and report["searchOpened"]
    assert report["emptySearch"] and report["comparisonPrompt"]
    assert report["reviewItems"]
    assert judgement.run(sample.model, sample.meaning, sample.facts)[0] in report["findingText"]


def test_self_map_language_rule_is_in_the_page_and_component_rules() -> None:
    """Acceptance: the language rule is visible in the page and every component in its scope."""
    root = Path(__file__).resolve().parent.parent
    cfg = config.load(root)
    model, meaning = config.load_model(root / "map/model.py")
    tokens = theme.resolve({}, all_layers(model, meaning))
    rule = next(inv for inv in model.invariants if "ASD-STE100 Issue 9" in inv.text)
    assert "AGENTS.md, Language requirement" in rule.text
    assert {"Agent", "Skill", "Scaffold", "SecondOpinion", "Page", "CLI"} <= set(rule.governs)
    _, details = render(model, meaning, tokens, {})
    data = json.loads(details)
    assert next(row for row in data["_meta"]["rules"] if row["n"] == rule.n)["text"] == rule.text
    for component in rule.governs:
        assert rule.n in data[component]["rules"]
    html = page.build(cfg, model, meaning, tokens, {}, {})
    assert rule.text in html
