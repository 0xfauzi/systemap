"""Review stamps survive runtime changes and reopen when reviewed evidence changes."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from systemap import card_review, delta, evidence, extract, history, journey_coverage
from systemap.config import Config
from systemap.model import Component, Flow, Journey, Meaning, Model, Step


def _model(*cards: Component, flows: tuple[Flow, ...] = ()) -> Model:
    return Model((800, 600), (), (), cards, flows, ("data",))


def _pending(
    model: Model, meaning: Meaning, base: dict[str, Any], head: dict[str, Any]
) -> list[delta.Line]:
    return delta._evidence_review_lines(
        Config(Path("."), "Example", ()),
        model,
        meaning,
        base,
        head,
        model,
        model,
        " at the base commit",
        "map/model.py",
    )


def test_python_syntax_hash_retains_python_311_representation(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("def f(x):\n return x\n")
    baseline = (
        "Module(body=[FunctionDef(name='f', args=arguments(posonlyargs=[], "
        "args=[arg(arg='x')], kwonlyargs=[], kw_defaults=[], defaults=[]), "
        "body=[Return(value=Name(id='x', ctx=Load()))], decorator_list=[])], type_ignores=[])"
    )
    record = extract.collect_module(source, tmp_path)
    assert record is not None
    assert record["syntax_sha"] == hashlib.sha256(baseline.encode()).hexdigest()[:16]
    source.write_text("# a comment\ndef f( x ):\n    return x\n")
    formatted = extract.collect_module(source, tmp_path)
    assert formatted is not None
    assert formatted["syntax_sha"] == record["syntax_sha"]
    source.write_text("def f(x):\n return x + 1\n")
    changed = extract.collect_module(source, tmp_path)
    assert changed is not None
    assert changed["syntax_sha"] != record["syntax_sha"]


def test_historical_cache_discards_pre_portability_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "pkg"
    source.mkdir()
    (source / "reader.py").write_text("def read():\n    return 1\n")
    for arguments in (
        ("init", "-q"),
        ("add", "."),
        (
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "source",
        ),
    ):
        subprocess.run(["git", "-C", str(tmp_path), *arguments], check=True)
    sha = delta.resolve(tmp_path, "HEAD")
    cfg = Config(tmp_path, "Example", (("pkg", "pkg"),))
    current_format = extract.FORMAT
    monkeypatch.setattr(extract, "FORMAT", 3)
    old = history.facts_at(cfg, sha)
    old["components"]["pkg.reader"]["syntax_sha"] = "obsolete-python-313-hash"
    cache = next(history.cache_dir(cfg).glob("*.json"))
    cache.write_text(json.dumps(old))
    monkeypatch.setattr(extract, "FORMAT", current_format)
    fresh = history.facts_at(cfg, sha)
    assert fresh["version"] == 4
    assert fresh["components"]["pkg.reader"]["syntax_sha"] != "obsolete-python-313-hash"


@pytest.mark.skipif(not hasattr(__import__("ast"), "TypeVar"), reason="Python 3.12 syntax")
def test_python_syntax_hash_retains_nonempty_type_parameters(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("def f[T](x: T) -> T:\n return x\n")
    original = extract.collect_module(source, tmp_path)
    source.write_text("def f[U](x: U) -> U:\n return x\n")
    changed = extract.collect_module(source, tmp_path)
    assert original is not None and changed is not None
    assert "parse_error" not in original and "parse_error" not in changed
    assert original["syntax_sha"] != changed["syntax_sha"]


def test_legacy_positional_journey_keeps_drafted_argument() -> None:
    step = Step(("Reader",), (), ("Reader", "Writer"), "Reads the input.")
    journey = Journey("read", "Read", (step,), "cli", True)
    assert journey.drafted is True
    assert journey.covers == ()
    assert journey_coverage.reviewed_entries((Meaning({}, journeys=(journey,)),)) == set()


@pytest.mark.parametrize("remove", [False, True])
def test_wildcard_membership_change_reopens_review(remove: bool) -> None:
    card = Component("Package", "Reads inputs.", implemented_by=("pkg.*",))
    model = _model(card)
    meaning = Meaning({"Package": "Package"})
    one = {"components": {"pkg.reader": {"syntax_sha": "reader"}}}
    two = copy.deepcopy(one)
    two["components"]["pkg.writer"] = {"syntax_sha": "writer"}
    base, head = (two, one) if remove else (one, two)
    stamp = card_review.digest(card, model, meaning, base)
    assert stamp is not None
    reviewed = dataclasses.replace(card, source_review=stamp)
    old_model = _model(reviewed)
    pending = _pending(old_model, meaning, base, head)
    assert [(line.kind, line.cards) for line in pending] == [("source review", ("Package",))]
    assert "pkg.writer" in pending[0].text
    fresh = card_review.digest(reviewed, old_model, meaning, head)
    assert fresh is not None
    assert (
        _pending(_model(dataclasses.replace(reviewed, source_review=fresh)), meaning, base, head)
        == []
    )


@pytest.mark.parametrize("keep_import", [True, False])
def test_changed_reviewed_flow_references_reopen_delta(keep_import: bool) -> None:
    cards = (
        Component("Reader", "Reads input.", implemented_by=("pkg.reader",)),
        Component("Writer", "Writes output.", implemented_by=("pkg.writer",)),
    )
    flow = Flow("Reader", "Writer", "input", "data", ("pkg.reader@" + "a" * 64,))
    meaning = Meaning({}, relations={flow.edge: "Sends input."})
    flow = dataclasses.replace(flow, review_digest=evidence.flow_claim_digest(flow, meaning))
    model = _model(*cards, flows=(flow,))
    base: dict[str, Any] = {
        "components": {
            "pkg.reader": {
                "syntax_sha": "reader",
                "source_sha256": "a" * 64,
                "uses": {"pkg.writer": []},
            },
            "pkg.writer": {"syntax_sha": "writer", "source_sha256": "b" * 64},
        }
    }
    head = copy.deepcopy(base)
    head["components"]["pkg.reader"]["source_sha256"] = "c" * 64
    if not keep_import:
        head["components"]["pkg.reader"]["uses"] = {}
    assert evidence.of_model(model, meaning, base)[flow.edge].state == evidence.OBSERVED
    pending = _pending(model, meaning, base, head)
    assert len(pending) == 1
    assert pending[0].kind == ("source evidence lost" if keep_import else "evidence lost")
    assert pending[0].decide
    fresh_flow = dataclasses.replace(flow, source_refs=("pkg.reader@" + "c" * 64,))
    assert _pending(_model(*cards, flows=(fresh_flow,)), meaning, base, head) == []
