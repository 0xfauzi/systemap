"""A current answer from systemap 2.0.0 stays current after the update (issue 90).

systemap 2.0.0 recorded the evidence digest of an answer in an earlier form: the full module
records and the source files. Acceptance values, for a Python fixture and a TypeScript
fixture:

1. An answer with a 2.0.0 digest that agrees with the source is current after one
   `systemap extract`. The command wrote the current digest in place of the 2.0.0 digest,
   and changed no other text of the configuration file. This is also true for an item in
   the earlier `crossing import` line form. A second `extract` writes nothing.
2. An answer with a 2.0.0 digest that does not agree with the source (a comment changed
   after the answer) stays pending, and `extract` writes nothing.
3. On 3.1.0 and on 4.0.0, `extract` also does the replacement of acceptance 1 (issue 143).

A probe on this repository gave the evidence: the earlier form gave the 6 digests that
80e418b recorded in `systemap.toml`.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from conftest import give_module_roles, set_version
from test_answer_identity import append, case, project, structural_lines

from systemap import (
    answer_write,
    card_review,
    config,
    extract,
    judgement,
    judgement_evidence,
    judgement_json,
    nest,
)
from systemap.cli import main

__all__ = ["project"]


def digests(root: Path, lines: list[str], earlier: bool) -> dict[str, str]:
    cfg = config.load(root)
    facts = extract.build(cfg)
    return judgement.evidence_for_tree(nest.load(cfg), facts, root, lines, earlier=earlier)


def answer_earlier(root: Path) -> tuple[list[str], dict[str, str]]:
    """Record two answers with 2.0.0 digests: a `single module` line, and a `crossing
    import` line in its earlier form with the count. Give the lines and the digests."""
    single, crossing = structural_lines(root)[:2]
    # A handoff module role opens the import crossing, so its answer is not hidden.
    give_module_roles(root)
    earlier = digests(root, [single, crossing], earlier=True)
    old_crossing = crossing.replace(" and no flow", " in 1 module and no flow")
    cfg = config.load(root)
    answer_write.add(
        root,
        cfg.source,
        [
            {"item": single, "reason": "A test.", "evidence": earlier[single]},
            {"item": old_crossing, "reason": "A test.", "evidence": earlier[crossing]},
        ],
    )
    return [single, crossing], earlier


def pending(root: Path) -> list[str]:
    cfg = config.load(root)
    facts = extract.build(cfg)
    return judgement_json.evaluate(nest.load(cfg), facts, cfg).result.pending


def test_a_current_answer_from_2_0_0_gets_the_current_digest(project: Path) -> None:
    """Acceptance 1."""
    lines, earlier = answer_earlier(project)
    toml = project / "systemap.toml"
    before = toml.read_text(encoding="utf-8")
    assert len(pending(project)) == 2
    assert main(["--root", str(project), "extract"]) == 0
    now = digests(project, lines, earlier=False)
    expected = before
    for line in lines:
        expected = expected.replace(earlier[line], now[line])
    assert toml.read_text(encoding="utf-8") == expected != before
    assert pending(project) == []
    assert main(["--root", str(project), "extract"]) == 0
    assert toml.read_text(encoding="utf-8") == expected


def test_an_answer_from_2_0_0_that_does_not_agree_stays_pending(project: Path) -> None:
    """Acceptance 2."""
    answer_earlier(project)
    c = case(project)
    append(project, c["file"], c["comment"])
    toml = project / "systemap.toml"
    before = toml.read_text(encoding="utf-8")
    assert main(["--root", str(project), "extract"]) == 0
    assert toml.read_text(encoding="utf-8") == before
    assert len(pending(project)) == 2


@pytest.mark.parametrize("version", ["3.1.0", "4.0.0"])
def test_a_later_version_also_upgrades_an_answer_from_2_0_0(
    project: Path, version: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 3."""
    set_version(monkeypatch, version)
    lines, earlier = answer_earlier(project)
    toml = project / "systemap.toml"
    before = toml.read_text(encoding="utf-8")
    assert main(["--root", str(project), "extract"]) == 0
    now = digests(project, lines, earlier=False)
    expected = before
    for line in lines:
        expected = expected.replace(earlier[line], now[line])
    assert toml.read_text(encoding="utf-8") == expected != before
    assert pending(project) == []


def _with_import_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Give a copy of the facts with the format 15 import keys in each module record."""
    changed = copy.deepcopy(facts)
    for record in changed["components"].values():
        targets = sorted(record.get("uses", {}))
        # A `type` form removes an import crossing (stage 3). The `call` and `load` forms
        # keep it, so the same lines have a digest.
        record["import_forms"] = {target: ["call", "load"] for target in targets}
        record["dynamic_imports"] = [{"call": "import", "text": "", "target": "", "line": 1}]
    return changed


def test_the_import_facts_of_format_15_do_not_change_the_evidence(project: Path) -> None:
    """The 2.0.0 digest, the cited facts and the source review digest do not read the
    `import_forms` and `dynamic_imports` keys (facts format 15)."""
    cfg = config.load(project)
    facts = extract.build(cfg)
    changed = _with_import_facts(facts)
    tree = nest.load(cfg)
    lines = structural_lines(project)[:2]
    for earlier in (True, False):
        assert judgement.evidence_for_tree(
            tree, changed, project, lines, earlier=earlier
        ) == judgement.evidence_for_tree(tree, facts, project, lines, earlier=earlier)
    for name, record in facts["components"].items():
        new = changed["components"][name]
        assert judgement_evidence.cited_facts(new) == judgement_evidence.cited_facts(record)
    model, meaning = tree.maps[0].model, tree.maps[0].meaning
    for card in model.components:
        assert card_review.digest(card, model, meaning, changed) == card_review.digest(
            card, model, meaning, facts
        )
